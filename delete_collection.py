from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

# 连接 Milvus
connections.connect(
    host="localhost",
    port="19530"
)

collection_name = "agent_memory"

# ===================== 强制删除旧集合 =====================
if utility.has_collection(collection_name):
    coll = Collection(collection_name)
    coll.drop()
    print("✅ 已删除旧集合：agent_memory")

# ===================== 新建 千问 1024 维度集合 =====================
pk = FieldSchema(
    name="pk",
    dtype=DataType.INT64,
    is_primary=True,
    auto_id=True
)
vector = FieldSchema(
    name="vector",
    dtype=DataType.FLOAT_VECTOR,
    dim=1024  # 千问专用！
)
agent_id = FieldSchema(
    name="agent_id",
    dtype=DataType.VARCHAR,
    max_length=255
)
confidence = FieldSchema(
    name="confidence",
    dtype=DataType.FLOAT
)
page_content = FieldSchema(
    name="page_content",
    dtype=DataType.VARCHAR,
    max_length=65535
)

schema = CollectionSchema(
    fields=[pk, vector, agent_id, confidence, page_content],
    description="CRAG 千问向量库"
)

# 正确创建集合
coll = Collection(
    name=collection_name,
    schema=schema,
    using="default"
)

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