from app.tool.base import BaseTool
from pydantic import Field
import PyPDF2
import re

class ResearchTools(BaseTool):
    """
    科研综合工具（三合一）
    - 论文阅读
    - 文献分析
    - 读书报告生成
    符合 OpenManus MCP 标准
    """
    name: str = "research_tools"
    description: str = "科研综合工具：阅读论文、分析文献、生成读书报告"
    
    mode: str = Field(..., description="运行模式：read | analyze | report")
    file_path: str = Field(..., description="论文PDF路径")

    async def execute(self, mode: str, file_path: str):
        try:
            # 1. 读取PDF全文
            full_text = self._read_pdf(file_path)

            # 2. 根据模式执行
            if mode == "read":
                return self._read_paper(full_text)
            elif mode == "analyze":
                return self._analyze_paper(full_text)
            elif mode == "report":
                return self._generate_report(full_text)
            else:
                return "❌ 不支持的模式，请输入 read/analyze/report"
                
        except Exception as e:
            return f"❌ 执行失败：{str(e)}"

    # ======================
    # 内部工具方法
    # ======================
    def _read_pdf(self, path):
        text = ""
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n\n"
        return text

    def _read_paper(self, text):
        abstract = self._extract_section(text, "abstract", "introduction")
        conclusion = self._extract_section(text, "conclusion", "references")
        return f"""【论文摘要】
{abstract[:5000]}

【结论】
{conclusion[:5000]}"""

    def _analyze_paper(self, text):
        core_idea = self._extract_section(text, "abstract", "introduction")
        methods = text.lower().find("method")
        results = text.lower().find("result")
        return f"""【文献分析报告】
核心创新点：{core_idea[:3000]}
方法概述：{text[methods:results][:3000]}
结果总结：{text[results:results+5000]}"""

    def _generate_report(self, text):
        return f"""【科研读书报告】
1. 研究目标：{self._extract_section(text, 'abstract', 'introduction')[:2000]}
2. 研究方法：{self._extract_section(text, 'method', 'result')[:2000]}
3. 实验结果：{self._extract_section(text, 'result', 'conclusion')[:2000]}
4. 结论与展望：{self._extract_section(text, 'conclusion', 'reference')[:2000]}
5. 可复现点：本文可复现的核心模块包括模型结构、数据集、实验流程。
6. 改进方向：待补充。"""

    def _extract_section(self, text, start_key, end_key):
        start = text.lower().find(start_key)
        end = text.lower().find(end_key)
        if start == -1:
            return "未找到章节"
        if end == -1:
            return text[start:start+10000]
        return text[start:end]