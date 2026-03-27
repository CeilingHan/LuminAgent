import os
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

# ===================== 配置千问 API KEY =====================
os.environ["DASHSCOPE_API_KEY"] = "sk-807195fcd0d54f29b8117e7e9ad32c98"
# 【重要】在当前目录新建 test.txt 文件
TEXT_PATH = "test.txt"

# ===================== 1. 加载文档 =====================
loader = TextLoader(TEXT_PATH, encoding="utf-8")
documents = loader.load()

# ===================== 2. 文本分块 =====================
splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=20
)
split_docs = splitter.split_documents(documents)

# ===================== 3. 向量化 =====================
embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# ===================== 4. 构建向量库 =====================
db = FAISS.from_documents(split_docs, embedding)
retriever = db.as_retriever(search_kwargs={"k": 1})

# ===================== 5. 接入千问大模型 =====================
llm = ChatOpenAI(
    model="qwen-turbo",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ["DASHSCOPE_API_KEY"]
)

# ===================== 6. RAG 问答链 =====================
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever
)

# ===================== 测试提问 =====================
query = "我的名字是什么？"
result = qa_chain.run(query)
print("回答：", result)