from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import uuid
import asyncio
from fastapi.responses import StreamingResponse
from app.tool.research_pipeline import ResearchPipeline
import json

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ======================
# 全局只保存 agent，不保存 flow
# ======================
agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    try:
        from app.agent.manus import Manus
        from app.tool import BrowserUseTool, StrReplaceEditor, Terminate, ToolCollection
        from app.tool.python_execute import PythonExecute
        from app.tool.research_tools import ResearchTools

        agent = Manus(
            available_tools=ToolCollection(
                PythonExecute(),
                BrowserUseTool(),
                ResearchTools(),
                StrReplaceEditor(),
                Terminate(),
            )
        )
        print("✅ OpenManus 启动成功！")
    except Exception as e:
        print(f"❌ 启动失败：{e}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def get_root():
    """返回 Agent 基本信息和可用技能"""
    global agent
    skills = []
    if agent and hasattr(agent, "available_tools"):
        for tool in agent.available_tools.tools:
            skills.append({
                "id": tool.name,
                "name": tool.name,
                "description": tool.description,
                "tags": ["工具"]
            })
    
    return {
        "name": "Manus Agent",
        "version": "0.1.0",
        "status": "online",
        "skills": skills
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, filename)

    with open(save_path, "wb") as f:
        f.write(await file.read())

    return {
        "filename": file.filename,
        "save_path": save_path,
        "message": "上传成功"
    }

# ======================
# ✅ 修复核心：每次都创建新 flow！
# ======================
@app.post("/execute")
async def execute(body: dict):
    try:
        from app.tool.research_tools import ResearchTools
        from app.llm import LLM
        from app.schema import Message

        prompt = body.get("prompt") or body.get("message", "")
        if isinstance(prompt, dict):
            import json
            prompt = json.dumps(prompt, ensure_ascii=False)
        file_path = body.get("file_path", "")

        if file_path and os.path.exists(file_path):
            lower_prompt = (prompt or "").lower()
            mode = "report"
            if "摘要" in prompt or "总结" in prompt or "summary" in lower_prompt or "abstract" in lower_prompt:
                mode = "read"
            if "分析" in prompt or "analy" in lower_prompt:
                mode = "analyze"
            if "报告" in prompt or "读书报告" in prompt or "report" in lower_prompt:
                mode = "report"

            tool_result = await ResearchTools().execute(mode=mode, file_path=file_path)
            return {"success": True, "result": tool_result.output or ""}

        llm = LLM()
        answer = await llm.ask(messages=[Message.user_message(prompt or "")], stream=False)
        return {"success": True, "result": answer}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"执行失败：{str(e)}"}



@app.post("/execute/stream")
async def execute_stream(body: dict):
    async def generate():
        try:
            from app.tool.research_tools import ResearchTools
            from app.llm import LLM
            from app.schema import Message
            import json

            prompt = body.get("prompt") or body.get("message", "")
            if isinstance(prompt, dict):
                prompt = json.dumps(prompt, ensure_ascii=False)

            file_path = body.get("file_path", "")
            llm = LLM()

            if file_path and os.path.exists(file_path):
                lower_prompt = (prompt or "").lower()
                mode = "report"
                if "摘要" in prompt or "总结" in prompt or "summary" in lower_prompt:
                    mode = "read"
                elif "分析" in prompt or "analy" in lower_prompt:
                    mode = "analyze"

                yield f"data: {json.dumps({'type': 'status', 'content': '📄 正在读取PDF...'}, ensure_ascii=False)}\n\n"
                tool = ResearchTools()
                content = tool._extract_multimodal_content(file_path)

                yield f"data: {json.dumps({'type': 'status', 'content': '🧠 正在分析论文，请稍候...'}, ensure_ascii=False)}\n\n"
                messages = tool._build_messages(mode, content)

                # 转成 dict 列表
                messages_dict = [m.to_dict() for m in messages]
            else:
                messages_dict = [{"role": "user", "content": prompt or ""}]

            # 直接调用底层 client 流式接口
            response = await llm.client.chat.completions.create(
                model=llm.model,
                messages=messages_dict,
                stream=True,
                max_tokens=4096,
            )

            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'type': 'text', 'content': delta}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


from app.tool.research_pipeline import ResearchPipeline

@app.post("/research/pipeline")
async def research_pipeline(body: dict):
    async def generate():
        import json
        file_path = body.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            yield f"data: {json.dumps({'type':'error','content':'文件不存在'}, ensure_ascii=False)}\n\n"
            return

        pipeline = ResearchPipeline()
        async for event in pipeline.run(file_path):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/download/{filename}")
async def download_file(filename: str):
    from fastapi.responses import FileResponse
    file_path = f"uploads/{filename}"
    if not os.path.exists(file_path):
        return {"error": "文件不存在"}
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
