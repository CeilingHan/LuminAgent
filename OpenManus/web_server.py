from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import json
import logging
from fastapi.responses import StreamingResponse
from app.tool.research_pipeline import ResearchPipeline
from app.tool.web_search import WebSearch

# Initialize LangSmith tracing at startup
from app.tracer import init_langsmith
init_langsmith()

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Tool availability check (run at startup) ──

def _check_tool_available(import_path: str) -> bool:
    """Check if a tool's dependencies are available by attempting import."""
    try:
        if "." in import_path:
            module_path, attr = import_path.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_path)
            return hasattr(mod, attr) or True
        else:
            import importlib
            importlib.import_module(import_path)
            return True
    except ImportError:
        return False


# Known tools — their actual availability is checked at startup.
# Tools that fail the import check are marked available=false so the
# frontend can disable / grey them out.
def _build_available_tools() -> list:
    checks = [
        ("python_execute",     "PythonExecute",      "Execute Python code in a sandboxed environment", "app.tool.python_execute"),
        ("web_search",         "WebSearch",          "Multi-engine web search (Google/Baidu/DuckDuckGo/Bing)", "app.tool.web_search"),
        ("browser_use",        "BrowserUseTool",     "Automate web browser interactions", "app.tool.browser_use_tool"),
        ("str_replace_editor", "StrReplaceEditor",   "View, create, and edit files", "app.tool.str_replace_editor"),
        ("research_tools",     "ResearchTools",      "PDF paper analysis and report generation", "app.tool.research_tools"),
        ("terminate",          "Terminate",          "Signal task completion", "app.tool.terminate"),
        ("bash",               "Bash",               "Execute shell commands in a sandbox", "app.tool.bash"),
        ("planning",           "PlanningTool",       "Create and manage execution plans", "app.tool.planning"),
    ]
    tools = []
    for tid, name, desc, import_path in checks:
        available = _check_tool_available(import_path)
        tools.append({
            "id": tid,
            "name": name,
            "description": desc,
            "available": available,
            "tags": ["工具"],
        })
    return tools


AVAILABLE_TOOLS = _build_available_tools()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on server boot, shut it down on server exit."""
    from app.scheduler import scheduler_manager
    scheduler_manager.start()
    yield
    scheduler_manager.shutdown(wait=False)


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
    return {
        "name": "Manus Agent",
        "version": "0.1.0",
        "status": "online",
        "skills": AVAILABLE_TOOLS,
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

@app.post("/execute")
async def execute(body: dict):
    """同步聊天端点（前端 ApiTest/EmailTest 等测试页使用）"""
    try:
        from app.llm import LLM
        from app.schema import Message

        prompt = body.get("prompt") or body.get("message", "")
        if isinstance(prompt, dict):
            prompt = json.dumps(prompt, ensure_ascii=False)
        if not prompt:
            return {"success": False, "error": "缺少 prompt"}

        llm = LLM()
        answer = await llm.ask(messages=[Message.user_message(prompt)], stream=False)
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


# ======================
# Python 代码直接执行端点
# ======================
@app.post("/execute/python")
async def execute_python(body: dict):
    """直接执行 Python 代码（绕过 LLM 意图分析）。

    前端用户直接写/粘贴 Python 代码时使用此端点，
    不走 analyze_intent → LLM 生成代码的流程。

    Body: {"code": "print(1+1)\\nprint('hello')", "timeout": 10}
    """
    async def generate():
        import json

        code = body.get("code", "")
        timeout = body.get("timeout", 5)

        if not code or not code.strip():
            yield _sse("error", "缺少 code 参数")
            return

        yield _sse("status", "🐍 执行 Python 代码...")

        from app.tool.python_execute import PythonExecute
        result = await PythonExecute().execute(code=code.strip(), timeout=timeout)

        observation = result.get("observation", str(result))
        success = result.get("success", False)

        if success:
            yield _sse("status", "✅ 执行成功")
        else:
            yield _sse("status", "❌ 执行出错")
        yield _sse("tool_result", content=observation[:2000])
        yield _sse("done", "")

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── 代码检测：判断用户输入是否像可直接执行的 Python 代码 ──

_CODE_INDICATORS: tuple = (
    "print(", "def ", "class ", "import ", "from ",
    "for ", "while ", "if ", "elif ", "else:",
    "with ", "try:", "except ", "finally:",
    "return ", "yield ", "lambda ",
    "__name__", "__main__",
    "=", "+=", "-=", "*=", "/=",
)

def _looks_like_python_code(prompt: str) -> bool:
    """Quick heuristic to detect if a user prompt looks like raw Python code.

    Checks for:
    - Multi-line content (contains \\n)
    - Python keywords / patterns at the start of lines
    - Assignment operators
    - Shebang or coding declarations
    """
    if not prompt:
        return False

    p = prompt.strip()

    # Multi-line code — almost certainly code, not NL prompt
    if "\n" in p:
        # Check if any line starts with a Python keyword
        lines = [l.strip() for l in p.split("\n") if l.strip()]
        code_lines = sum(
            1 for line in lines
            if line.startswith(_CODE_INDICATORS) or any(line.startswith(kw) for kw in ("print(", "def ", "class ", "import ", "from ", "for ", "while ", "if ", "with "))
        )
        if code_lines >= 1:
            return True
        # Pure multi-line assignment/expression
        if all("=" in line or line.startswith(("#", "\"", "'")) for line in lines[:3]):
            return True

    # Single-line: starts with Python keyword or print
    for indicator in _CODE_INDICATORS:
        if p.startswith(indicator):
            return True

    # Looks like a Python expression using assignment
    if p.startswith("#") or p.startswith("\"\"\"") or p.startswith("'''"):
        return True

    return False


# ======================
# Agent 流式端点 (v2: 工具路由)
# ======================
@app.post("/agent/stream")
async def agent_stream(body: dict):
    """智能工具路由 + 流式回答。

    意图分析 → 工具选择 → 工具执行 → LLM 合成回答。
    支持: web_search, python_execute, browser_use, str_replace_editor, chat
    """
    async def generate():
        import json

        prompt = body.get("prompt") or body.get("message", "")
        if isinstance(prompt, dict):
            prompt = json.dumps(prompt, ensure_ascii=False)
        if not prompt.strip():
            yield _sse("error", "请输入指令")
            return

        enable_tools = bool(body.get("enable_tools", True))

        try:
            from datetime import datetime
            from app.memory_manager import get_memory_manager
            from app.skill_manager import get_skill_manager

            today_str = datetime.now().strftime("%Y年%m月%d日")

            # ── Load memory context (MEMORY.md + recent memories) ──
            memory_ctx = ""
            try:
                mm = get_memory_manager()
                memory_ctx = mm.get_relevant_context(query=prompt, limit=3)
            except Exception:
                pass  # memory is optional — don't fail the request

            # ── Load skill context (explicit skill_name or trigger keywords) ──
            skill_ctx = ""
            skill_name = body.get("skill_name", "").strip()
            try:
                sm = get_skill_manager()
                if skill_name:
                    # Explicit skill selected by user via / command
                    skill = sm.get(skill_name)
                    if skill:
                        skill_ctx = (
                            "<active-skills>\n"
                            f"<!-- Skill: {skill['name']} — {skill['description']} -->\n"
                            + skill["content"]
                            + "\n</active-skills>\n"
                        )
                        yield _sse("status", f"🎯 已激活技能: {skill['name']}")
                    else:
                        # Maybe it's a built-in tool name — create a minimal context
                        skill_ctx = f"<active-skills>\n<!-- Using tool: {skill_name} -->\n请使用 {skill_name} 工具来完成用户的任务。\n</active-skills>\n"
                else:
                    # Auto-match by trigger keywords
                    skill_ctx = sm.get_matching_context(prompt)
            except Exception:
                pass  # skills are optional

            # ── Phase 0: 工具已禁用 → 直接聊天 ──
            if not enable_tools:
                yield _sse("status", "💬 工具模式已关闭，直接回答...")
                messages = [
                    {"role": "system", "content": f"{skill_ctx}{memory_ctx}你是一个智能助手。今天是{today_str}。请直接、准确地回答用户的问题。使用 Markdown 格式。"},
                    {"role": "user", "content": prompt},
                ]
                async for delta in _stream_llm(messages):
                    yield _sse("text", delta)
                return

            # ── Phase 0: 代码检测快捷路径 ──
            # 如果用户输入像 Python 代码，跳过意图分析，直接执行
            if _looks_like_python_code(prompt):
                yield _sse("status", "🐍 检测到 Python 代码，直接执行...")
                yield _sse("tool_call", tools=["python_execute"], args=[json.dumps({"code": prompt[:200]}, ensure_ascii=False)])

                from app.tool.python_execute import PythonExecute
                result = await PythonExecute().execute(code=prompt.strip())
                observation = result.get("observation", str(result))
                success = result.get("success", False)

                if success:
                    yield _sse("status", "✅ 执行成功")
                else:
                    yield _sse("status", "❌ 执行出错")
                yield _sse("tool_result", content=observation[:2000])

                # LLM explain the result
                explain_messages = [
                    {"role": "system", "content": f"你是一个 Python 代码助手。今天是{today_str}。请根据用户输入的代码和执行结果，简洁地解释代码做了什么以及输出含义。使用中文。如果代码有错误，帮用户分析原因。"},
                    {"role": "user", "content": f"代码：\n```python\n{prompt[:2000]}\n```\n\n执行结果：\n{observation[:1000]}"},
                ]
                async for delta in _stream_llm(explain_messages):
                    yield _sse("text", delta)
                return

            # ── Phase 1: 意图分析 + 工具选择 ──
            yield _sse("status", "🧠 分析问题意图...")

            from app.tool.intent_analyzer import analyze_intent

            intent = await analyze_intent(prompt, today_str)

            tool_name = intent.get("tool", "chat")
            reasoning = intent.get("reasoning", "")
            yield _sse("status", f"📋 意图: {reasoning}")

            # Build tool_call args for frontend display
            tool_params = {
                k: v for k, v in intent.items()
                if k not in ("tool", "reasoning") and v
            }
            yield _sse("tool_call", tools=[tool_name], args=[json.dumps(tool_params, ensure_ascii=False)])

            # ── Phase 2: 工具分发 (callback-based SSE) ──
            tool_output: Optional[str] = None
            search_results = []
            sse_events: list = []  # collects SSE strings emitted by handlers

            def emit(event_type: str, content: str = "", **extra):
                sse_events.append(_sse(event_type, content, **extra))

            if tool_name == "web_search":
                tool_output, search_results = await _handle_web_search(prompt, emit)

            elif tool_name == "python_execute":
                tool_output = await _handle_python_execute(intent, emit)

            elif tool_name == "browser_use":
                tool_output = await _handle_browser_use(intent, emit)

            elif tool_name == "str_replace_editor":
                tool_output = await _handle_str_replace_editor(intent, emit)

            # tool == "chat" → tool_output stays None, answer directly

            # Flush collected SSE events
            for evt in sse_events:
                yield evt

            # ── Phase 3: LLM 合成回答 ──
            messages = _build_synthesize_messages(
                prompt=prompt,
                tool_name=tool_name,
                tool_output=tool_output,
                search_results=search_results,
                today_str=today_str,
                memory_context=memory_ctx,
                skill_context=skill_ctx,
            )

            async for delta in _stream_llm(messages):
                yield _sse("text", delta)

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse("error", str(e))

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── SSE helpers ───────────────────────────────────────────────

def _sse(event_type: str, content: str = "", **extra) -> str:
    """Build a single SSE data line."""
    import json
    payload = {"type": event_type}
    if content:
        payload["content"] = content
    payload.update(extra)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_llm(messages: list):
    """Yield content deltas from a streaming LLM call."""
    from app.llm import LLM

    llm = LLM()
    response = await llm.client.chat.completions.create(
        model=llm.model,
        messages=messages,
        stream=True,
        max_tokens=llm.max_tokens,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ── Tool handlers (emit SSE via callback, return result) ──────────

async def _handle_web_search(prompt: str, emit) -> tuple:
    """Execute web_search tool. Returns (tool_output_str, search_results_list)."""
    ws = WebSearch()
    sr = await ws.search_with_intent(prompt)

    if sr["should_search"] and sr["results"]:
        emit("search_result",
             query=sr["search_queries"][0] if sr["search_queries"] else prompt,
             results=sr["results"])
        status_msg = (
            f"📄 找到 {sr['total_results']} 条去重结果，"
            f"覆盖 {sr['unique_domains']} 个不同来源，正在分析..."
        )
        emit("status", status_msg)
        output = _format_search_context(sr["results"])
        emit("tool_result", content=output[:500])
        return output, sr["results"]
    elif sr["should_search"]:
        emit("status", "⚠️ 未搜到结果，用已有知识回答")
        return None, []
    else:
        emit("status", "💬 无需搜索，直接回答...")
        return None, []


async def _handle_python_execute(intent: dict, emit) -> Optional[str]:
    """Execute python_execute tool. Returns observation string."""
    from app.tool.python_execute import PythonExecute

    code = intent.get("python_code", "")
    if not code:
        emit("status", "⚠️ 未生成代码，跳过执行")
        return None

    emit("status", "🐍 执行 Python 代码...")
    result = await PythonExecute().execute(code=code)
    observation = result.get("observation", str(result))
    success = result.get("success", False)
    label = "✅ 执行成功" if success else "❌ 执行出错"
    emit("status", label)
    emit("tool_result", content=observation[:1000])
    return observation


async def _handle_browser_use(intent: dict, emit) -> Optional[str]:
    """Execute browser_use tool. Returns output string."""
    from app.tool.browser_use_tool import BrowserUseTool

    action = intent.get("browser_action", "web_search")
    query = intent.get("browser_query", "")
    url = intent.get("browser_url", "")

    emit("status", f"🌐 浏览器操作: {action}...")
    tool = BrowserUseTool()
    try:
        result = await tool.execute(action=action, query=query, url=url)
        output = result.output if hasattr(result, 'output') else str(result)
        if hasattr(result, 'error') and result.error:
            emit("status", f"⚠️ 浏览器操作出错: {result.error}")
        else:
            emit("status", "✅ 浏览器操作完成")
        emit("tool_result", content=output[:1000])
        return output
    except Exception as e:
        emit("status", f"❌ 浏览器操作失败: {e}")
        return f"[Browser error: {e}]"
    finally:
        try:
            await tool.cleanup()
        except Exception:
            pass


async def _handle_str_replace_editor(intent: dict, emit) -> Optional[str]:
    """Execute str_replace_editor tool. Returns result string."""
    from app.tool.str_replace_editor import StrReplaceEditor

    command = intent.get("file_command", "view")
    file_path = intent.get("file_path", "")

    if not file_path:
        emit("status", "⚠️ 未指定文件路径")
        return None

    emit("status", f"📝 文件操作: {command} {file_path}...")
    try:
        tool = StrReplaceEditor()
        kwargs = {"command": command, "path": file_path}
        if command == "create":
            kwargs["file_text"] = intent.get("file_text", "")
        elif command == "str_replace":
            kwargs["old_str"] = intent.get("old_str", "")
            kwargs["new_str"] = intent.get("new_str", "")

        result_str = await tool.execute(**kwargs)
        emit("status", "✅ 文件操作完成")
        emit("tool_result", content=result_str[:1000])
        return result_str
    except Exception as e:
        emit("status", f"❌ 文件操作失败: {e}")
        return f"[File operation error: {e}]"


# ── Context builders ─────────────────────────────────────────

def _format_search_context(results: list) -> str:
    """Format search results as a plain-text context block for the synthesizing LLM."""
    lines = ["以下是网络搜索结果：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"**结果 {i}**: {r.get('title', '')}")
        lines.append(f"  链接: {r.get('url', '')}")
        if r.get("description"):
            lines.append(f"  摘要: {r['description']}")
        if r.get("content_preview"):
            lines.append(f"  内容: {r['content_preview']}")
        lines.append("")
    return "\n".join(lines)


def _build_synthesize_messages(
    prompt: str,
    tool_name: str,
    tool_output: Optional[str],
    search_results: list,
    today_str: str,
    memory_context: str = "",
    skill_context: str = "",
) -> list:
    """Build the messages for the final LLM synthesizer based on tool and output."""

    # System prompt varies by tool
    system_prompts = {
        "web_search": (
            f"你是一个智能助手。今天是{today_str}。请根据提供的网络搜索结果回答用户问题。\n"
            "要求：\n"
            "1. 综合搜索结果中的信息，给出准确、有条理的回答\n"
            f"2. 用户问题中说的「今天」/「现在」，就是{today_str}。如果搜索结果的时间与{today_str}不匹配，必须明确指出\n"
            "3. 如果搜索结果不足以回答问题，请诚实说明\n"
            "4. 使用 Markdown 格式让回答更易读"
        ),
        "python_execute": (
            f"你是一个智能助手。今天是{today_str}。用户运行了 Python 代码，输出结果如下。\n"
            "请根据代码输出解释结果，用自然语言回答用户的问题。\n"
            "如果代码报错，请帮助用户分析错误原因并给出修正建议。\n"
            "使用 Markdown 格式让回答更易读。"
        ),
        "browser_use": (
            f"你是一个智能助手。今天是{today_str}。用户浏览了网页，获取到以下内容。\n"
            "请根据网页内容整理信息，回答用户的问题。\n"
            "如果内容是搜索结果，请综合各条信息给出答案。\n"
            "使用 Markdown 格式让回答更易读。"
        ),
        "str_replace_editor": (
            f"你是一个智能助手。今天是{today_str}。用户对文件进行了操作，结果如下。\n"
            "请说明操作是否成功，展示关键结果，并回答用户的问题。\n"
            "使用 Markdown 格式让回答更易读。"
        ),
        "chat": (
            f"你是一个智能助手。今天是{today_str}。请直接、准确地回答用户的问题。"
            "使用 Markdown 格式让回答更易读。"
        ),
    }

    system_content = system_prompts.get(
        tool_name,
        system_prompts["chat"],
    )

    # Prepend skill context then memory context if available
    if skill_context:
        system_content = skill_context + "\n" + system_content
    if memory_context:
        system_content = memory_context + "\n" + system_content

    messages = [{"role": "system", "content": system_content}]

    # Build user message with tool context
    user_parts = []

    if tool_name == "web_search" and search_results:
        user_parts.append(_format_search_context(search_results))
        user_parts.append(f"用户问题：{prompt}")
    elif tool_output:
        user_parts.append("以下是工具执行结果：\n")
        user_parts.append("```")
        user_parts.append(tool_output[:3000] if len(tool_output) > 3000 else tool_output)
        user_parts.append("```")
        user_parts.append(f"\n用户问题：{prompt}")
    else:
        user_parts.append(prompt)

    messages.append({"role": "user", "content": "\n".join(user_parts)})
    return messages


# ── Plan mode helpers (defined in app/scheduler.py, imported here) ──
from app.scheduler import create_plan, PLAN_CREATION_SYSTEM  # noqa: E402


async def _execute_plan_step(
    step_text: str, today_str: str, emit
) -> tuple:
    """Execute one plan step using intent analysis + tool dispatch.

    Returns (success: bool, output: str).
    """
    from app.tool.intent_analyzer import analyze_intent

    emit("status", f"🔍 分析步骤意图: {step_text[:80]}...")

    try:
        intent = await analyze_intent(step_text, today_str)
    except Exception as e:
        emit("status", f"⚠️ 意图分析失败: {e}, 使用 LLM 直接处理")
        intent = {"tool": "chat", "reasoning": "analysis failed"}

    tool_name = intent.get("tool", "chat")
    tool_params = {
        k: v for k, v in intent.items()
        if k not in ("tool", "reasoning") and v
    }
    emit("tool_call", tools=[tool_name], args=[_json_dumps(tool_params)])

    tool_output = None
    search_results = []

    if tool_name == "web_search":
        tool_output, search_results = await _handle_web_search(step_text, emit)
    elif tool_name == "python_execute":
        tool_output = await _handle_python_execute(intent, emit)
    elif tool_name == "browser_use":
        tool_output = await _handle_browser_use(intent, emit)
    elif tool_name == "str_replace_editor":
        tool_output = await _handle_str_replace_editor(intent, emit)
    elif tool_name == "chat":
        # Generate a brief LLM answer for this step
        from app.llm import LLM
        llm = LLM()
        step_messages = _build_synthesize_messages(
            prompt=step_text,
            tool_name="chat",
            tool_output=None,
            search_results=[],
            today_str=today_str,
        )
        response = await llm.client.chat.completions.create(
            model=llm.model,
            messages=step_messages,
            max_tokens=llm.max_tokens,
            stream=False,
        )
        tool_output = response.choices[0].message.content.strip()

    success = tool_output is not None
    return success, (tool_output or ""), search_results


def _json_dumps(obj, default_val="{}"):
    """Safe json.dumps."""
    import json
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return default_val


# ── Plan stream endpoint ────────────────────────────────────

@app.post("/plan/stream")
async def plan_stream(body: dict):
    """Plan-then-Execute stream endpoint.

    Phase 1: LLM generates a plan → SSE plan_created
    Phase 2: Execute each step → SSE step_start / step_completed + tool events
    Phase 3: LLM summary → SSE text
    """
    async def generate():
        import json as _json

        prompt = body.get("prompt") or body.get("message", "")
        if isinstance(prompt, dict):
            prompt = _json.dumps(prompt, ensure_ascii=False)
        if not prompt.strip():
            yield _sse("error", "请输入指令")
            return

        try:
            from datetime import datetime
            today_str = datetime.now().strftime("%Y年%m月%d日")

            # ── Phase 1: Generate Plan ──
            yield _sse("status", "📋 正在生成执行计划...")
            plan = await create_plan(prompt, today_str)
            yield _sse("status", f"📋 计划已生成: {plan['title']} ({len(plan['steps'])} 步)")

            yield _sse(
                "plan_created",
                plan_id=plan["plan_id"],
                title=plan["title"],
                steps=[
                    {"text": s, "status": st}
                    for s, st in zip(plan["steps"], plan["step_statuses"])
                ],
            )

            # ── Phase 2: Execute Steps ──
            sse_events: list = []

            def emit(event_type: str, content: str = "", **extra):
                sse_events.append(_sse(event_type, content, **extra))

            step_results = []

            for i, step_text in enumerate(plan["steps"]):
                yield _sse("step_start", step_index=i, step_text=step_text)
                yield _sse("status", f"🔄 [{i+1}/{len(plan['steps'])}] {step_text[:100]}")

                # Flush prior events
                for evt in sse_events:
                    yield evt
                sse_events.clear()

                success, output, _ = await _execute_plan_step(
                    step_text, today_str, emit
                )

                # Flush events generated by this step
                for evt in sse_events:
                    yield evt
                sse_events.clear()

                step_results.append({
                    "index": i,
                    "text": step_text,
                    "success": success,
                    "output": output[:800] if output else "",
                })

                if success:
                    yield _sse("step_completed", step_index=i)
                else:
                    yield _sse("step_error", step_index=i, error=output[:200])

            # ── Phase 3: LLM Summary ──
            yield _sse("status", "📝 生成总结...")

            # Build summary context
            results_text = "\n".join(
                f"Step {r['index']+1}: {r['text']}\n  Result: {r['output'][:300]}"
                for r in step_results
            )
            summary_messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a helpful assistant. Today is {today_str}. "
                        "The user asked you to complete a task, and you have finished all steps. "
                        "Summarize what was accomplished in a clear, concise way. "
                        "If there were errors, mention them honestly. Use the user's language (Chinese if the task was in Chinese). "
                        "Use Markdown for readability."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Original task: {prompt}\n\nPlan title: {plan['title']}\n\nStep results:\n{results_text}\n\nPlease provide a summary.",
                },
            ]
            async for delta in _stream_llm(summary_messages):
                yield _sse("text", delta)

            yield _sse("done", "")

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse("error", str(e))

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Memory REST endpoints ────────────────────────────────────

@app.get("/memory")
async def memory_list():
    """List all memories from MEMORY.md index."""
    from app.memory_manager import get_memory_manager
    try:
        mm = get_memory_manager()
        items = mm.list_all()
        return {
            "success": True,
            "data": [
                {
                    "name": i.name,
                    "description": i.description,
                    "type": i.type.value,
                    "content_preview": i.content[:200] if i.content else "",
                    "links": i.links,
                    "created_at": i.created_at,
                    "updated_at": i.updated_at,
                }
                for i in items
            ],
            "total": len(items),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/memory/{name}")
async def memory_get(name: str):
    """Read a single memory file."""
    from app.memory_manager import get_memory_manager
    try:
        mm = get_memory_manager()
        item = mm.read_memory(name)
        if not item:
            return {"success": False, "error": f"Memory '{name}' not found"}
        return {
            "success": True,
            "data": {
                "name": item.name,
                "description": item.description,
                "type": item.type.value,
                "content": item.content,
                "metadata": item.metadata,
                "links": item.links,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/memory")
async def memory_create(body: dict):
    """Create or update a memory. Body: {name, type, description, content}."""
    from app.memory_manager import get_memory_manager
    from app.schema import MemoryItem, MemoryType
    try:
        name = body.get("name", "").strip()
        if not name:
            return {"success": False, "error": "name is required"}

        mm = get_memory_manager()

        # Check if updating existing
        existing = mm.read_memory(name)
        if existing:
            existing.description = body.get("description", existing.description)
            existing.content = body.get("content", existing.content)
            if "type" in body:
                existing.type = MemoryType(body["type"])
            existing.links = body.get("links", existing.links)
            mm.write_memory(existing)
            return {"success": True, "data": {"name": existing.name, "action": "updated"}}

        item = MemoryItem(
            name=name,
            description=body.get("description", ""),
            type=MemoryType(body.get("type", "project")),
            content=body.get("content", ""),
            links=body.get("links", []),
            metadata=body.get("metadata", {}),
        )
        mm.write_memory(item)
        return {"success": True, "data": {"name": item.name, "action": "created"}}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/memory/{name}")
async def memory_delete(name: str):
    """Delete a memory."""
    from app.memory_manager import get_memory_manager
    try:
        mm = get_memory_manager()
        mm.delete_memory(name)
        return {"success": True, "message": f"Memory '{name}' deleted"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/memory/search")
async def memory_search(body: dict):
    """Search memories by keyword. Body: {query, limit}."""
    from app.memory_manager import get_memory_manager
    try:
        query = body.get("query", "").strip()
        if not query:
            return {"success": False, "error": "query is required"}
        limit = body.get("limit", 10)
        mm = get_memory_manager()
        results = mm.search(query, limit=limit)
        return {
            "success": True,
            "data": [
                {
                    "name": r.name,
                    "description": r.description,
                    "type": r.type.value,
                    "content_preview": r.content[:300] if r.content else "",
                    "updated_at": r.updated_at,
                }
                for r in results
            ],
            "total": len(results),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Skills REST endpoints ────────────────────────────────────

@app.get("/skills")
async def skills_list():
    """List all skills."""
    from app.skill_manager import get_skill_manager
    try:
        sm = get_skill_manager()
        skills = sm.list_all()
        return {
            "success": True,
            "data": [
                {
                    "name": s["name"],
                    "description": s["description"],
                    "tools": s.get("tools", []),
                    "trigger_keywords": s.get("trigger_keywords", []),
                    "content_preview": s["content"][:200] if s["content"] else "",
                    "source_url": s.get("source_url"),
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at"),
                }
                for s in skills
            ],
            "total": len(skills),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/skills/{name}")
async def skills_get(name: str):
    """Read a single skill file."""
    from app.skill_manager import get_skill_manager
    try:
        sm = get_skill_manager()
        skill = sm.get(name)
        if not skill:
            return {"success": False, "error": f"Skill '{name}' not found"}
        return {"success": True, "data": skill}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/skills")
async def skills_create(body: dict):
    """Create or update a skill. Body: {name, description, tools, trigger_keywords, content}."""
    from app.skill_manager import get_skill_manager
    try:
        name = body.get("name", "").strip()
        if not name:
            return {"success": False, "error": "name is required"}
        sm = get_skill_manager()
        result = sm.create_or_update({
            "name": name,
            "description": body.get("description", ""),
            "tools": body.get("tools", []),
            "trigger_keywords": body.get("trigger_keywords", []),
            "content": body.get("content", ""),
        })
        return {"success": True, "data": {"name": result["name"], "action": result.get("action", "created")}}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/skills/{name}")
async def skills_delete(name: str):
    """Delete a skill."""
    from app.skill_manager import get_skill_manager
    try:
        sm = get_skill_manager()
        sm.delete(name)
        return {"success": True, "message": f"Skill '{name}' deleted"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/skills/load")
async def skills_load_from_url(body: dict):
    """Load a skill from a URL. Body: {url}."""
    from app.skill_manager import get_skill_manager
    try:
        url = body.get("url", "").strip()
        if not url:
            return {"success": False, "error": "url is required"}
        sm = get_skill_manager()
        result = await sm.load_from_url(url)
        return {
            "success": True,
            "data": {
                "name": result["name"],
                "description": result["description"],
                "action": result.get("action", "loaded"),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Scheduler REST endpoints ─────────────────────────────────

@app.get("/scheduler/jobs")
async def scheduler_list_jobs():
    """List all scheduled tasks."""
    from app.scheduler import scheduler_manager
    try:
        jobs = scheduler_manager.get_jobs()
        return {"success": True, "data": jobs, "total": len(jobs)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/scheduler/jobs")
async def scheduler_create_job(body: dict):
    """Create a new scheduled task."""
    from app.scheduler import scheduler_manager
    try:
        name = body.get("name", "").strip()
        cron = body.get("cron", "").strip()
        prompt = body.get("prompt", "").strip()
        mode = body.get("mode", "agent")

        if not name:
            return {"success": False, "error": "name is required"}
        if not cron:
            return {"success": False, "error": "cron is required"}
        if not prompt:
            return {"success": False, "error": "prompt is required"}

        job = scheduler_manager.add_job(name=name, cron=cron, prompt=prompt, mode=mode)
        return {"success": True, "data": job}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/scheduler/jobs/{job_id}")
async def scheduler_delete_job(job_id: str):
    """Delete a scheduled task."""
    from app.scheduler import scheduler_manager
    try:
        ok = scheduler_manager.remove_job(job_id)
        if ok:
            return {"success": True, "message": f"Job {job_id} removed"}
        else:
            return {"success": False, "error": f"Job {job_id} not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/scheduler/jobs/{job_id}")
async def scheduler_toggle_job(job_id: str):
    """Toggle a scheduled task enabled/disabled."""
    from app.scheduler import scheduler_manager
    try:
        jdef = scheduler_manager.toggle_job(job_id)
        return {"success": True, "data": jdef}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/scheduler/jobs/{job_id}/history")
async def scheduler_job_history(job_id: str, limit: int = 10):
    """Get execution history for a scheduled task."""
    from app.scheduler import scheduler_manager
    try:
        history = scheduler_manager.get_history(job_id, limit=limit)
        return {"success": True, "data": history, "total": len(history)}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
