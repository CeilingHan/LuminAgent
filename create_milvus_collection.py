from pymilvus import connections, CollectionSchema, FieldSchema, DataType, utility

# 连接
connections.connect(host="localhost", port="19530")

# 先删除旧集合（因为维度不对）
collection_name = "agent_memory"
if utility.has_collection(collection_name):
    coll = utility.get_collection(collection_name)
    coll.drop()
    print("🗑️ 已删除旧集合（维度不匹配）")

# 千问向量维度 = 1024 【关键修复】
vector = FieldSchema(
    name="vector",
    dtype=DataType.FLOAT_VECTOR,
    dim=1024  # 这里必须是 1024！
)

pk = FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True)
agent_id = FieldSchema(name="agent_id", dtype=DataType.VARCHAR, max_length=255)
confidence = FieldSchema(name="confidence", dtype=DataType.FLOAT)
page_content = FieldSchema(name="page_content", dtype=DataType.VARCHAR, max_length=65535)

schema = CollectionSchema(
    fields=[pk, vector, agent_id, confidence, page_content],
    description="CRAG Agent Memory (Qwen 1024 dim)"
)

# 创建
coll = utility.create_collection(collection_name, schema)

# 创建索引
coll.create_index(
    field_name="vector",
    index_params={
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
)

print("✅ 千问专用 Milvus 集合创建成功！维度=1024")