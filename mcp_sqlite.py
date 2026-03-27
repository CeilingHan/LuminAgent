import os
import sqlite3
import json
import dashscope
from dashscope import Generation
from dotenv import load_dotenv

# 加载环境变量（存放LLM API Key）
load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")  # 从.env文件读取，避免硬编码

# ===================== 1. 初始化本地数据库（示例） =====================
def init_local_db(db_path: str = "emotion_data.db"):
    """创建本地SQLite数据库和情感标注表，插入测试数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建情感标注表（模拟你的业务表结构）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emotion_annotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id TEXT NOT NULL,
        person_id TEXT NOT NULL,
        initial_emotion TEXT NOT NULL,
        final_emotion TEXT NOT NULL,
        start_time FLOAT NOT NULL,
        end_time FLOAT NOT NULL,
        reasoning TEXT
    )
    ''')
    
    # 插入测试数据
    test_data = [
        ("4", "P1", "happy", "joyful", 245.0, 247.0, "笑容明显，肢体放松"),
        ("4", "P1", "neutral", "calm", 0.0, 6.5, "面部无明显情绪，动作平缓"),
        ("5", "P2", "angry", "frustrated", 100.0, 105.0, "皱眉，语速加快"),
    ]
    cursor.executemany('''
    INSERT OR IGNORE INTO emotion_annotations 
    (video_id, person_id, initial_emotion, final_emotion, start_time, end_time, reasoning)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', test_data)
    
    conn.commit()
    conn.close()
    print(f"✅ 本地数据库初始化完成：{db_path}")

# ===================== 2. MCP协议封装LLM请求（核心） =====================
def generate_sql_via_mcp(natural_query: str, table_schema: str) -> str:
    """
    按MCP规范调用LLM，将自然语言查询转换为SQL
    :param natural_query: 用户自然语言查询（如"查询video_id=4的所有情感标注"）
    :param table_schema: 数据库表结构（MCP上下文，让LLM了解表信息）
    :return: LLM生成的SQL语句
    """
    # MCP规范Prompt（标准化LLM输入，提升SQL生成准确性）
    mcp_prompt = f"""
    ### MCP Context: Database Query
    你是一个遵循MCP协议的SQL生成助手，仅处理SELECT查询，禁止DELETE/UPDATE/INSERT/DROP等操作。
    数据库表结构：
    {table_schema}
    
    ### User Request (Natural Language):
    {natural_query}
    
    ### Response Format (Strict SQL Only):
    仅返回可执行的SQL语句，无需解释、无需多余文本，示例：
    SELECT * FROM emotion_annotations WHERE video_id = '4';
    """
    
    # 调用通义千问LLM（兼容其他LLM，只需替换调用方式）
    try:
        response = Generation.call(
            model="qwen-turbo",  # 轻量版，也可用qwen-plus/qwen-max
            messages=[{"role": "user", "content": mcp_prompt}],
            result_format="text",
            temperature=0.1,  # 低温度，保证SQL生成稳定
            max_tokens=1000
        )
        if response.status_code == 200:
            sql = response.output.text.strip()
            # 基础SQL安全校验（仅允许SELECT）
            if not sql.upper().startswith("SELECT"):
                raise ValueError(f"非法SQL操作：{sql}，仅允许SELECT查询")
            return sql
        else:
            raise Exception(f"LLM调用失败：{response.message}")
    except Exception as e:
        print(f"❌ SQL生成失败：{e}")
        return ""

# ===================== 3. 执行SQL并返回结果 =====================
def query_local_db(db_path: str, sql: str) -> list:
    """执行SQL查询本地数据库，返回结果"""
    if not sql:
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 让结果支持列名索引
        cursor = conn.cursor()
        cursor.execute(sql)
        # 转换为字典列表（更易读）
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        print(f"❌ SQL执行失败：{e}")
        return []

# ===================== 4. 结果转换为自然语言（MCP闭环） =====================
def format_result_to_natural_language(results: list, natural_query: str) -> str:
    """将数据库查询结果转换为自然语言（MCP最终返回给用户）"""
    if not results:
        return f"未找到与「{natural_query}」匹配的数据"
    
    # 调用LLM格式化结果（也可手动格式化，简化版）
    prompt = f"""
    将以下数据库查询结果转换为自然语言回答，保持简洁易懂：
    查询需求：{natural_query}
    查询结果：{json.dumps(results, ensure_ascii=False, indent=2)}
    """
    try:
        response = Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}],
            result_format="text",
            temperature=0.3
        )
        return response.output.text.strip() if response.status_code == 200 else json.dumps(results, ensure_ascii=False)
    except:
        # 降级方案：直接返回JSON格式
        return json.dumps(results, ensure_ascii=False, indent=2)

# ===================== 5. 主流程：自然语言→SQL→数据库→自然语言 =====================
def main_mcp_db_query(natural_query: str, db_path: str = "emotion_data.db"):
    """
    主函数：通过MCP协议实现自然语言查询本地数据库
    :param natural_query: 用户自然语言查询
    :param db_path: 本地数据库路径
    """
    # 步骤1：初始化数据库（首次运行执行）
    if not os.path.exists(db_path):
        init_local_db(db_path)
    
    # 步骤2：定义表结构（MCP上下文，需和实际表一致）
    table_schema = """
    表名：emotion_annotations
    列名及类型：
    - id: INTEGER（主键）
    - video_id: TEXT（视频ID）
    - person_id: TEXT（人物ID）
    - initial_emotion: TEXT（初始情感标签）
    - final_emotion: TEXT（最终情感标签）
    - start_time: FLOAT（开始时间，秒）
    - end_time: FLOAT（结束时间，秒）
    - reasoning: TEXT（情感推理说明）
    """
    
    # 步骤3：MCP调用LLM生成SQL
    print(f"🔍 处理自然语言查询：{natural_query}")
    sql = generate_sql_via_mcp(natural_query, table_schema)
    if not sql:
        print("❌ 未生成合法SQL")
        return
    print(f"📝 LLM生成的SQL：{sql}")
    
    # 步骤4：执行SQL查询本地数据库
    results = query_local_db(db_path, sql)
    print(f"📊 数据库查询结果：{results}")
    
    # 步骤5：转换为自然语言返回
    natural_result = format_result_to_natural_language(results, natural_query)
    print(f"\n✅ 最终回答：\n{natural_result}")

# ===================== 运行示例 =====================
if __name__ == "__main__":
    # 示例1：简单查询
    main_mcp_db_query("查询video_id=5的所有情感标注数据")
    
    # 示例2：复杂条件查询
    # main_mcp_db_query("查询person_id=P1且initial_emotion=neutral的标注，返回video_id、start_time和reasoning")
    
    # 示例3：统计查询
    # main_mcp_db_query("统计每个video_id下的情感标注数量")