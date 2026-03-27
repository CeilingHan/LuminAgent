from pymilvus import connections, Collection

connections.connect(host="localhost", port="19530")

coll = Collection("agent_memory")
coll.load()

print("数据条数：", coll.num_entities)