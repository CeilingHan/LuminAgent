from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import uuid
import asyncio

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
        agent = Manus()
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
        from app.flow.flow_factory import FlowFactory, FlowType

        prompt = body.get("prompt", "")
        file_path = body.get("file_path", "")

        if file_path and os.path.exists(file_path):
            prompt = f"{prompt}\n文件路径: {file_path}"

        # ✅ 每次请求都创建新 flow
        flow = FlowFactory.create_flow(
            flow_type=FlowType.PLANNING,
            agents={"manus": agent}
        )

        result = await asyncio.wait_for(
            flow.execute(prompt),
            timeout=3600
        )

        final = str(result).split("Terminated:")[0].split("Step 20:")[-1].strip()
        return {"success": True, "result": final}

    except Exception as e:
        return {"success": False, "error": f"执行失败：{str(e)}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)