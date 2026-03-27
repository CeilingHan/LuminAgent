import os
from typing import Literal, List
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.llms import Tongyi
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel
from pymilvus import connections, Collection

# ===================== 配置 =====================
os.environ["DASHSCOPE_API_KEY"] = "sk-807195fcd0d54f29b8117e7e9ad32c98"

# ===================== 连接 Milvus =====================
connections.connect(host="localhost", port="19530")
coll = Collection("agent_memory")
coll.load()

# ===================== 模型 =====================
embed = DashScopeEmbeddings(model="text-embedding-v2")
llm = Tongyi(model="qwen-turbo", temperature=0.1)

# ===================== 【高级评估器】带置信度 + 可解释 =====================
class RelevanceVerdict(BaseModel):
    verdict: Literal["relevant", "ambiguous", "incorrect"]
    confidence: float
    reasoning: str

# 千问专用评估提示词
grader_prompt = PromptTemplate(
    template="""
你是文档相关性评估专家。

查询：{query}
文档：{document}

请严格按JSON输出，不要多余内容：
{{
    "verdict": "relevant / ambiguous / incorrect",
    "confidence": 0.0~1.0,
    "reasoning": "简要判断依据"
}}
""",
    input_variables=["query", "document"]
)

grader_chain = grader_prompt | llm | StrOutputParser()

# ===================== CRAG 核心逻辑 =====================
class CRAG:
    def __init__(self, agent_id="default"):
        self.agent_id = agent_id

    def retrieve(self, query):
        vector = embed.embed_query(query)
        res = coll.search(
            data=[vector],
            anns_field="vector",
            param={"metric_type": "COSINE"},
            limit=3,
            output_fields=["page_content", "agent_id", "confidence"]
        )
        docs = []
        for hit in res[0]:
            doc = Document(
                page_content=hit.entity.get("page_content", ""),
                metadata={
                    "agent_id": hit.entity.get("agent_id", ""),
                    "confidence": hit.entity.get("confidence", 0.0)
                }
            )
            docs.append(doc)
        return docs

    def evaluate(self, query, docs):
        if not docs:
            return {"verdict": "incorrect", "confidence": 0.0, "reasoning": "无文档"}

        doc_text = "\n".join([d.page_content[:600] for d in docs[:3]])
        try:
            import json
            raw = grader_chain.invoke({"query": query, "document": doc_text})
            return json.loads(raw)
        except:
            return {"verdict": "ambiguous", "confidence": 0.5, "reasoning": "评估失败"}

    def refine(self, docs, query):
        keywords = query.split()
        refined = []
        for doc in docs:
            sents = doc.page_content.replace("。", "。\n").split("\n")
            good = [s.strip() for s in sents if any(kw in s for kw in keywords)]
            if good:
                refined.append(Document(page_content="".join(good[:3])))
        return refined or docs

    def ask(self, query):
        # 1. 检索
        docs = self.retrieve(query)
        # 2. 评估
        eval_result = self.evaluate(query, docs)
        verdict = eval_result["verdict"]
        # 3. 精炼
        refined = self.refine(docs, query)

        # 4. 构造上下文
        ctx = "\n".join([d.page_content for d in refined[:3]])
        if not ctx:
            ctx = "未找到相关信息"

        # 5. 生成回答
        prompt = ChatPromptTemplate.from_messages([
            ("system", "根据以下资料回答，不要编造：\n{context}"),
            ("human", "{question}")
        ])
        chain = prompt | llm | StrOutputParser()
        return chain.invoke({"context": ctx, "question": query})

# ===================== 运行 =====================
if __name__ == "__main__":
    crag = CRAG(agent_id="test_user")
    print("回答：", crag.ask("你是谁？你来自哪？"))