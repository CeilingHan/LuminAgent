from asyncio.log import logger
import time
from app.tool.base import BaseTool
from app.llm import LLM
from app.schema import Message
import pdfplumber
import fitz  # PyMuPDF
import base64
import os
import re
from pathlib import Path
# 文件顶部加
from typing import ClassVar, Optional
from fastapi.responses import StreamingResponse
import json



class ResearchTools(BaseTool):
    name: str = "research_tools"
    description: str = "科研综合工具：深度阅读论文、分析文献、生成读书报告（支持图表理解）"
    PROMPTS: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["read", "analyze", "report"],
                "description": "运行模式：read | analyze | report",
            },
            "file_path": {
                "type": "string",
                "description": "论文PDF文件的本地路径",
            },
        },
        "required": ["mode", "file_path"],
    }

    # ============================================================
    # Prompt 模板
    # ============================================================
    PROMPTS = {
        "read": """你是一位顶尖 CV 领域研究员，正在阅读一篇 CVPR/ECCV/ICCV 级别的论文。
论文内容包括：提取的文字、结构化表格数据、以及关键页面的图像（含架构图、实验图）。

请结合所有信息，输出以下结构：

## 📌 研究问题与动机
（解决什么问题？现有方法的痛点？）

## 🏗️ 方法架构
（核心模型/算法是什么？关键模块有哪些？结合架构图描述数据流）

## 📊 实验结果
（在哪些 benchmark 上测试？关键指标是什么？比 SOTA 高多少？）

## 🔬 消融实验
（哪些模块贡献最大？去掉哪个组件性能下降最多？）

## 💡 核心创新点（3条以内，精炼）

## ⚠️ 局限性与未来工作""",

        "analyze": """你是一位顶级会议的 Area Chair，正在审阅这篇论文。
你能看到论文的文字内容、表格数据和图像。

请给出严格的学术评审分析：

## 🔬 技术新颖性评估
（创新点是否真正新颖？还是工程堆砌？与已有工作的本质区别？）

## 🧪 实验严谨性
（数据集选择是否合理？baseline 是否公平？有无 cherry-picking？
消融实验是否充分验证了每个设计决策？）

## 📐 方法论分析
（核心 loss 函数/模块设计的动机是否充分？理论支撑是否完备？）

## 📈 结果可信度
（提升幅度是否显著？在不同场景下的泛化性如何？）

## 🔗 与相关工作的差异
（与最近 1-2 年的同类工作相比，本质区别在哪？）

## 📝 审稿意见（Weakness 为主）
（如果你是审稿人，你会提什么质疑？）

## 🌟 综合评分
（创新性 / 实验充分性 / 写作清晰度，各 1-5 分）""",

        "report": """你是一位专业的科研读书报告撰写者，同时具备计算机视觉领域的专业背景。
你能看到论文的完整文字、表格和关键图像。

请生成一份完整、专业的读书报告：

## 一、研究背景与问题定义
（领域现状、现有方法不足、本文要解决的核心问题）

## 二、方法详解
（整体架构 → 关键模块 → 技术细节，结合架构图逐步描述）

## 三、实验配置
（数据集、评估指标、实现细节、训练配置）

## 四、实验结果分析
（主实验对比表格解读 → 消融实验解读 → 可视化结果分析）

## 五、核心贡献总结

## 六、批判性思考
（本文的不足之处？后续工作方向？对你自身研究的启发？）

请确保报告专业、深入，总字数不少于 1200 字。""",
    }

    # ============================================================
    # 主入口
    # ============================================================
    async def execute(self, mode: str, file_path: str, **kwargs):
        try:
            # print(f"[1] 开始处理文件: {file_path}")
            
            if not os.path.exists(file_path):
                return self.fail_response(f"文件不存在：{file_path}")
            content = self._extract_multimodal_content(file_path)
            messages = self._build_messages(mode, content)
            start_time = time.time()
            llm = LLM()
            result = await llm.ask(messages=messages, stream=False)
            end_time = time.time()
            # logger.info(f"[5] LLM 返回完成，长度={len(result)}，耗时={end_time - start_time} 秒")   
            return self.success_response(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.fail_response(f"执行失败：{str(e)}")

    # ============================================================
    # 多模态内容提取
    # ============================================================
    def _extract_multimodal_content(self, file_path: str) -> dict:
        """
        提取论文的所有有效信息：
        - 文字（pdfplumber，保留双栏布局）
        - 表格（结构化提取）
        - 关键页图像（架构图页、实验结果页）
        """
        result = {
            "text": "",
            "tables": [],
            "key_page_images": [],  # base64 编码的关键页截图
            "page_count": 0,
        }

        # === 文字 + 表格提取（pdfplumber，比 PyPDF2 好很多）===
        with pdfplumber.open(file_path) as pdf:
            result["page_count"] = len(pdf.pages)
            text_parts = []

            for i, page in enumerate(pdf.pages):
                # 文字
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                if text:
                    text_parts.append(f"\n--- 第{i+1}页 ---\n{text}")

                # 表格（结构化）
                tables = page.extract_tables()
                for j, table in enumerate(tables):
                    if table and len(table) > 1:  # 过滤空表格
                        formatted = self._format_table(table, page_num=i+1, table_num=j+1)
                        result["tables"].append(formatted)

            result["text"] = "\n".join(text_parts)

        # === 关键页图像提取（PyMuPDF）===
        result["key_page_images"] = self._extract_key_page_images(file_path)

        return result

    def _format_table(self, table: list, page_num: int, table_num: int) -> str:
        """将二维数组表格格式化为 Markdown"""
        if not table:
            return ""
        lines = [f"\n【表格 P{page_num}-T{table_num}】"]
        for row in table:
            cleaned = [str(cell).strip() if cell else "" for cell in row]
            lines.append("| " + " | ".join(cleaned) + " |")
            if table.index(row) == 0:  # 表头分隔线
                lines.append("|" + "|".join(["---"] * len(row)) + "|")
        return "\n".join(lines)

    def _extract_key_page_images(self, file_path: str) -> list:
        """
        智能识别并截取关键页面为图像：
        - 第1页（摘要+概览图）
        - 包含架构图的页面（通常是 Figure 1/2）
        - 包含对比表格的页面
        - 最后2页（结论）
        """
        images = []
        doc = fitz.open(file_path)
        total_pages = len(doc)

        # 识别关键页：含大图或关键词的页面
        key_pages = set()
        key_pages.add(0)  # 第1页必选
        key_pages.add(min(1, total_pages - 1))  # 第2页（通常有架构图）
        key_pages.add(total_pages - 1)  # 最后1页
        if total_pages > 1:
            key_pages.add(total_pages - 2)  # 倒数第2页

        # 扫描含大图或"Table"/"Figure"关键词的页面
        for i, page in enumerate(doc):
            if i in key_pages:
                continue
            text = page.get_text().lower()
            image_list = page.get_images()
            # 页面包含图片 或 包含实验相关关键词
            if (len(image_list) > 0 and
                any(kw in text for kw in ["figure", "table", "architecture",
                                           "pipeline", "framework", "ablation",
                                           "comparison", "sota", "state-of-the-art"])):
                key_pages.add(i)

        # 最多取 8 页图像（控制 token 消耗）
        selected = sorted(key_pages)[:8]

        for page_idx in selected:
            page = doc[page_idx]
            # 150 DPI 渲染，平衡质量和 token
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append({
                "page": page_idx + 1,
                "base64": b64,
            })

        doc.close()
        return images

    # ============================================================
    # 构建多模态消息
    # ============================================================
    def _build_messages(self, mode: str, content: dict) -> list:
        system_prompt = self.PROMPTS[mode]
        text = content["text"]
        tables_text = "\n\n".join(content["tables"])

        truncated_text = text[:8000]
        if len(text) > 8000:
            truncated_text += f"\n\n...[中间省略，共{content['page_count']}页]...\n\n"
            truncated_text += text[-2000:]

        user_text = f"""{system_prompt}

---
## 论文文字内容（共{content['page_count']}页）
{truncated_text}

---
## 结构化表格
{tables_text[:4000] if tables_text else "（未提取到表格）"}

---
以下附有论文关键页面截图（页码：{[img['page'] for img in content['key_page_images']]}），请结合图像分析。
"""
    # 提取所有图片 base64
        images_b64 = [img["base64"] for img in content["key_page_images"]]

        # 用多模态工厂方法构建消息
        return [Message.user_message_multimodal(user_text, images_b64)]
    