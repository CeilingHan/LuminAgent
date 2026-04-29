import asyncio
import json
import os
from typing import ClassVar, AsyncGenerator
from app.tool.base import BaseTool
from app.tool.research_tools import ResearchTools
from app.tool.web_search import WebSearch
from app.tool.pptx_tool import PptxTool
from app.llm import LLM
from app.schema import Message


class ResearchPipeline:
    """全套科研助手流水线，支持并发搜索 + 流式输出"""

    def __init__(self):
        self.research_tool = ResearchTools()
        self.web_search = WebSearch()
        self.pptx_tool = PptxTool()
        self.llm = LLM()

    async def run(self, file_path: str) -> AsyncGenerator[dict, None]:
        """
        主流水线，yield dict 事件供 SSE 消费
        事件类型：stage / text / search_result / related / pptx / done / error
        """
        queue = asyncio.Queue()

        # ========== 阶段1：文献深度分析（流式）==========
        yield {"type": "stage", "content": "📄 阶段1/4：正在深度分析文献..."}

        report_text = ""
        try:
            content = self.research_tool._extract_multimodal_content(file_path)
            messages = self.research_tool._build_messages("report", content)
            messages_dict = [m.to_dict() for m in messages]

            response = await self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=messages_dict,
                stream=True,
                max_tokens=4096,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    report_text += delta
                    yield {"type": "text", "content": delta}

        except Exception as e:
            yield {"type": "error", "content": f"文献分析失败：{str(e)}"}
            return

        # ========== 提取关键词（用于搜索）==========
        yield {"type": "stage", "content": "🔍 阶段2/4：提取关键词并启动并发搜索..."}

        paper_title = ""
        keywords = []
        try:
            kw_response = await self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=[{
                    "role": "user",
                    "content": (
                        f"从以下报告提取：1)论文英文标题 2)3个核心技术关键词。"
                        f"只输出JSON，格式：{{\"title\":\"...\",\"keywords\":[\"...\",\"...\",\"...\"]}}\n\n{report_text[:2000]}"
                    )
                }],
                max_tokens=200,
            )
            kw_text = kw_response.choices[0].message.content.strip()
            kw_data = json.loads(
                kw_text.replace("```json", "").replace("```", "").strip()
            )
            paper_title = kw_data.get("title", "")
            keywords = kw_data.get("keywords", [])
        except Exception:
            paper_title = "科研文献"
            keywords = []

        # ========== 阶段2：并发搜索（哪个先完成先推送）==========
        search_queries = []
        if paper_title:
            search_queries.append(f"{paper_title} survey")
            search_queries.append(f"{paper_title} github code")
        if keywords:
            search_queries.append(
                f"site:paperswithcode.com {' '.join(keywords[:2])}"
            )

        search_results_all = []

        if search_queries:
            # 用 Queue 实现"谁先完成谁先推送"
            async def single_search(query: str, q: asyncio.Queue):
                try:
                    result = await self.web_search.execute(
                        query=query, num_results=3
                    )
                    await q.put({
                        "type": "search_result",
                        "query": query,
                        "content": result.output or "",
                        "results": [
                            {"title": r.title, "url": r.url, "desc": r.description}
                            for r in result.results
                        ]
                    })
                except Exception as e:
                    await q.put({
                        "type": "search_result",
                        "query": query,
                        "content": f"搜索失败：{str(e)}",
                        "results": []
                    })
                finally:
                    await q.put({"type": "_search_done"})

            search_queue = asyncio.Queue()
            # 同时启动所有搜索
            tasks = [
                asyncio.create_task(single_search(q, search_queue))
                for q in search_queries
            ]

            done_count = 0
            while done_count < len(search_queries):
                item = await search_queue.get()
                if item["type"] == "_search_done":
                    done_count += 1
                else:
                    search_results_all.append(item["content"])
                    yield item  # 立刻推送给前端

            await asyncio.gather(*tasks)

        # ========== 阶段3：PPT生成 + 搜索总结 并发 ==========
        yield {"type": "stage", "content": "🎨 阶段3/4：PPT生成 & 相关工作总结（并发）..."}

        pptx_path = (
            f"uploads/{paper_title[:20].replace(' ', '_').replace('/', '_')}.pptx"
        )

        # 两个任务并发
        async def make_ppt():
            return await self.pptx_tool.execute(
                report=report_text,
                title=paper_title or "科研文献分析报告",
                output_path=pptx_path,
            )

        async def summarize_related():
            if not search_results_all:
                return ""
            combined = "\n\n".join(search_results_all)[:3000]
            resp = await self.llm.client.chat.completions.create(
                model=self.llm.model,
                messages=[{
                    "role": "user",
                    "content": (
                        f"基于以下搜索结果，用中文总结相关工作、开源代码和对比方法（300字内）：\n\n{combined}"
                    )
                }],
                max_tokens=500,
            )
            return resp.choices[0].message.content.strip()

        ppt_result, related_summary = await asyncio.gather(
            make_ppt(), summarize_related()
        )

        # 推送相关工作总结
        if related_summary:
            yield {"type": "stage", "content": "📚 阶段4/4：相关工作整合完成"}
            yield {"type": "related", "content": related_summary}

        # 推送 PPT 完成
        filename = os.path.basename(pptx_path)
        yield {
            "type": "pptx",
            "content": pptx_path,
            "filename": filename,
            "title": paper_title,
        }
        yield {"type": "done"}