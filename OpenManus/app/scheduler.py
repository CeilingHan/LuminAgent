"""
Scheduled task manager — wraps APScheduler for cron-based recurring research tasks.

Jobs persist to data/scheduled_tasks.json. Execution results persist to
data/task_results/<job_id>/<timestamp>.json.
"""
import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from app.logger import logger

# ── Persistence paths ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TASKS_FILE = DATA_DIR / "scheduled_tasks.json"
RESULTS_DIR = DATA_DIR / "task_results"


# ── Plan creation prompt (used by both web_server and scheduler) ──

PLAN_CREATION_SYSTEM = """\
You are an expert planning assistant. Given a user's task, break it down into 3-7 concrete,
actionable steps. Each step should describe ONE clear action. Use tools to complete each step
(web_search, python_execute, browser_use, str_replace_editor, or plain reasoning).

Rules:
- Steps should be sequential and logical
- Each step should produce a visible result
- Keep step descriptions concise (one sentence each, in Chinese if the user wrote in Chinese)
- Prefer tools when they would help (search for info, execute code, browse URLs, edit files)

Output ONLY valid JSON, no markdown wrapping:
{"title": "Plan title (short, descriptive, in user's language)", "steps": ["Step 1 description", "Step 2 description", ...]}"""


async def create_plan(prompt: str, today_str: str) -> dict:
    """Call LLM to generate a plan with steps. Returns {plan_id, title, steps, step_statuses}."""
    import json as _json
    from app.llm import LLM

    llm = LLM()
    messages = [
        {"role": "system", "content": PLAN_CREATION_SYSTEM},
        {"role": "user", "content": f"Today is {today_str}. Please create a plan for this task:\n\n{prompt}"},
    ]
    response = await llm.client.chat.completions.create(
        model=llm.model,
        messages=messages,
        max_tokens=800,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        plan_data = _json.loads(raw)
    except _json.JSONDecodeError:
        plan_data = {
            "title": "Execution Plan",
            "steps": [s.strip("- ") for s in raw.split("\n") if s.strip() and not s.strip().startswith("{")],
        }
        if not plan_data["steps"]:
            plan_data["steps"] = ["Analyze the task", "Execute the task", "Verify results"]

    steps = plan_data.get("steps", [])
    if not steps:
        steps = ["Analyze the task", "Execute the task", "Verify results"]

    return {
        "plan_id": f"plan_{int(time.time())}",
        "title": plan_data.get("title", "Execution Plan"),
        "steps": steps,
        "step_statuses": ["not_started"] * len(steps),
    }

# ── Task definitions persisted to JSON ──
# Structure:
# {
#   "jobs": {
#     "job_uuid": {
#       "id": "uuid",
#       "name": "每天早上检查arXiv",
#       "cron": "0 8 * * *",
#       "prompt": "search arxiv for latest LLM papers",
#       "mode": "agent",
#       "enabled": true,
#       "created_at": "2026-06-08T10:00:00"
#     }
#   }
# }


def _load_task_defs() -> dict:
    """Load persisted task definitions from JSON file."""
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"jobs": {}}
    return {"jobs": {}}


def _save_task_defs(task_defs: dict) -> None:
    """Persist task definitions to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(task_defs, f, ensure_ascii=False, indent=2)


def _save_result(job_id: str, result: dict) -> str:
    """Save an execution result and return the file path."""
    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = job_dir / f"{ts}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            **result,
        }, f, ensure_ascii=False, indent=2)
    return str(filepath)


def _read_history(job_id: str, limit: int = 10) -> list:
    """Read execution history for a job, most recent first."""
    job_dir = RESULTS_DIR / job_id
    if not job_dir.exists():
        return []
    files = sorted(job_dir.glob("*.json"), reverse=True)
    results = []
    for fp in files[:limit]:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return results


class SchedulerManager:
    """Singleton manager wrapping APScheduler's AsyncIOScheduler.

    Handles:
    - Starting/stopping the scheduler
    - Loading persisted jobs on startup
    - CRUD for scheduled tasks
    - Executing research tasks when triggered
    - Persisting execution results
    """

    _instance: Optional["SchedulerManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SchedulerManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._task_defs: dict = {"jobs": {}}

    # ── lifecycle ──────────────────────────────────────────

    def start(self):
        """Start the scheduler and reload persisted tasks."""
        job_stores = {"default": MemoryJobStore()}
        self._scheduler = AsyncIOScheduler(
            jobstores=job_stores,
            timezone="Asia/Shanghai",
        )

        # Reload persisted tasks
        self._task_defs = _load_task_defs()
        reloaded = 0
        for job_id, jdef in self._task_defs.get("jobs", {}).items():
            if not jdef.get("enabled", True):
                continue
            try:
                self._scheduler.add_job(
                    func=_execute_scheduled_task,
                    trigger=CronTrigger.from_crontab(jdef["cron"]),
                    args=[job_id, jdef.get("prompt", ""), jdef.get("mode", "agent")],
                    id=job_id,
                    name=jdef.get("name", job_id),
                    replace_existing=True,
                )
                reloaded += 1
            except Exception as e:
                logger.warning(f"Failed to reload scheduled task {job_id}: {e}")

        self._scheduler.start()
        logger.info(f"Scheduler started with {reloaded} reloaded tasks")

    def shutdown(self, wait: bool = False):
        """Gracefully shut down the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=wait)
            logger.info("Scheduler shut down")

    # ── CRUD ───────────────────────────────────────────────

    def add_job(
        self,
        name: str,
        cron: str,
        prompt: str,
        mode: str = "agent",
        job_id: str = "",
        enabled: bool = True,
    ) -> dict:
        """Add a new scheduled task. Returns the job definition."""
        if not job_id:
            job_id = f"job_{int(time.time() * 1000)}"

        if not self._scheduler:
            raise RuntimeError("Scheduler not started")

        # Validate cron expression
        try:
            trigger = CronTrigger.from_crontab(cron)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{cron}': {e}")

        # Add to APScheduler (only if enabled)
        if enabled:
            self._scheduler.add_job(
                func=_execute_scheduled_task,
                trigger=trigger,
                args=[job_id, prompt, mode],
                id=job_id,
                name=name,
                replace_existing=True,
            )

        # Persist to JSON
        jdef = {
            "id": job_id,
            "name": name,
            "cron": cron,
            "prompt": prompt,
            "mode": mode,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
        }
        self._task_defs.setdefault("jobs", {})[job_id] = jdef
        _save_task_defs(self._task_defs)

        logger.info(f"Added scheduled task '{name}' (id={job_id}, cron={cron})")
        return jdef

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled task. Returns True if it existed."""
        existed = False

        if self._scheduler and self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            existed = True

        if job_id in self._task_defs.get("jobs", {}):
            del self._task_defs["jobs"][job_id]
            _save_task_defs(self._task_defs)
            existed = True

        if existed:
            logger.info(f"Removed scheduled task {job_id}")
        return existed

    def get_jobs(self) -> list:
        """List all jobs with their next run time."""
        jobs = []
        for job_id, jdef in self._task_defs.get("jobs", {}).items():
            entry = dict(jdef)  # copy
            # Add runtime info from scheduler
            aps_job = self._scheduler.get_job(job_id) if self._scheduler else None
            if aps_job:
                entry["next_run"] = aps_job.next_run_time.isoformat() if aps_job.next_run_time else None
            else:
                entry["next_run"] = None

            # Add last result summary
            history = _read_history(job_id, limit=1)
            if history:
                last = history[0]
                entry["last_run"] = last.get("timestamp", "")
                entry["last_success"] = last.get("success", False)
                entry["last_summary"] = (last.get("summary", "") or "")[:150]

            jobs.append(entry)

        # Sort by creation time, newest first
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
        return jobs

    def toggle_job(self, job_id: str) -> dict:
        """Toggle enable/disable for a job. Returns updated def."""
        jdef = self._task_defs.get("jobs", {}).get(job_id)
        if not jdef:
            raise ValueError(f"Job {job_id} not found")

        new_enabled = not jdef.get("enabled", True)
        jdef["enabled"] = new_enabled

        if new_enabled:
            # Re-add to scheduler
            try:
                trigger = CronTrigger.from_crontab(jdef["cron"])
                self._scheduler.add_job(
                    func=_execute_scheduled_task,
                    trigger=trigger,
                    args=[job_id, jdef["prompt"], jdef.get("mode", "agent")],
                    id=job_id,
                    name=jdef.get("name", job_id),
                    replace_existing=True,
                )
            except Exception as e:
                logger.error(f"Failed to re-enable job {job_id}: {e}")
                jdef["enabled"] = False
        else:
            if self._scheduler and self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

        _save_task_defs(self._task_defs)
        status = "enabled" if new_enabled else "disabled"
        logger.info(f"Toggled scheduled task {job_id}: {status}")
        return jdef

    def get_history(self, job_id: str, limit: int = 10) -> list:
        """Get execution history for a job."""
        jdef = self._task_defs.get("jobs", {}).get(job_id)
        if not jdef:
            raise ValueError(f"Job {job_id} not found")
        return _read_history(job_id, limit=limit)

    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running


# ── Singleton access ──
scheduler_manager = SchedulerManager()


# ── Job execution function (called by APScheduler when a job fires) ──

async def _execute_scheduled_task(job_id: str, prompt: str, mode: str = "agent"):
    """Core execution function invoked by the scheduler when a cron trigger fires.

    Executes the task through the same intent_analyzer + tool dispatch + LLM
    synthesize pipeline used by /agent/stream and /plan/stream.
    """
    logger.info(f"[{job_id}] Executing scheduled task (mode={mode}): {prompt[:100]}...")
    start_time = time.time()

    try:
        today_str = datetime.now().strftime("%Y年%m月%d日")

        if mode == "plan":
            # Use the plan-then-execute flow
            summary = await _run_plan_flow(prompt, today_str, job_id)
            _save_result(job_id, {
                "prompt": prompt,
                "mode": mode,
                "success": True,
                "summary": summary,
                "duration_s": round(time.time() - start_time, 1),
            })
        else:
            # Use the agent flow (intent → tool dispatch → synthesize)
            summary = await _run_agent_flow(prompt, today_str, job_id)
            _save_result(job_id, {
                "prompt": prompt,
                "mode": mode,
                "success": True,
                "summary": summary,
                "duration_s": round(time.time() - start_time, 1),
            })

        logger.info(f"[{job_id}] Task completed in {time.time() - start_time:.1f}s")
    except Exception as e:
        logger.error(f"[{job_id}] Task failed: {e}")
        import traceback
        traceback.print_exc()
        _save_result(job_id, {
            "prompt": prompt,
            "mode": mode,
            "success": False,
            "error": str(e),
            "duration_s": round(time.time() - start_time, 1),
        })


async def _run_agent_flow(prompt: str, today_str: str, job_id: str) -> str:
    """Execute a single prompt through the Agent flow and return the LLM's answer."""
    from app.tool.intent_analyzer import analyze_intent
    from app.tool.web_search import WebSearch
    from app.tool.python_execute import PythonExecute
    from app.tool.browser_use_tool import BrowserUseTool
    from app.tool.str_replace_editor import StrReplaceEditor
    from app.llm import LLM

    # Phase 1: Intent analysis
    intent = await analyze_intent(prompt, today_str)
    tool_name = intent.get("tool", "chat")
    logger.info(f"[{job_id}] Intent: {tool_name}")

    # Phase 2: Tool execution
    tool_output = None
    search_results = []

    if tool_name == "web_search":
        ws = WebSearch()
        sr = await ws.search_with_intent(prompt)
        if sr.get("results"):
            search_results = sr["results"]
            tool_output = _format_context(sr["results"])

    elif tool_name == "python_execute":
        code = intent.get("python_code", "")
        if code:
            result = await PythonExecute().execute(code=code)
            tool_output = result.get("observation", str(result))

    elif tool_name == "browser_use":
        action = intent.get("browser_action", "web_search")
        query = intent.get("browser_query", prompt)
        url = intent.get("browser_url", "")
        tool = BrowserUseTool()
        try:
            result = await tool.execute(action=action, query=query, url=url)
            tool_output = result.output if hasattr(result, 'output') else str(result)
        finally:
            try:
                await tool.cleanup()
            except Exception:
                pass

    elif tool_name == "str_replace_editor":
        command = intent.get("file_command", "view")
        file_path = intent.get("file_path", "")
        if file_path:
            kwargs = {"command": command, "path": file_path}
            if command == "create":
                kwargs["file_text"] = intent.get("file_text", "")
            elif command == "str_replace":
                kwargs["old_str"] = intent.get("old_str", "")
                kwargs["new_str"] = intent.get("new_str", "")
            try:
                result_str = await StrReplaceEditor().execute(**kwargs)
                tool_output = str(result_str)
            except Exception as e:
                tool_output = f"[Error: {e}]"

    # Phase 3: LLM synthesize
    system_prompt = (
        f"You are a research assistant. Today is {today_str}. "
        "Based on the tool results, provide a concise, informative answer. "
        "Use Markdown. Respond in Chinese if the task is in Chinese."
    )
    user_parts = []
    if tool_output:
        user_parts.append("Tool output:\n```")
        user_parts.append(tool_output[:3000])
        user_parts.append("```")
    if search_results:
        user_parts.append("\nSearch results:\n")
        user_parts.append(_format_context(search_results))
    user_parts.append(f"\nTask: {prompt}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_parts)},
    ]

    llm = LLM()
    response = await llm.client.chat.completions.create(
        model=llm.model,
        messages=messages,
        max_tokens=llm.max_tokens,
        stream=False,
    )
    answer = response.choices[0].message.content.strip()
    return answer


async def _run_plan_flow(prompt: str, today_str: str, job_id: str) -> str:
    """Execute through the Plan flow and return the summary."""
    from app.llm import LLM

    plan = await create_plan(prompt, today_str)
    step_summaries = []

    for i, step_text in enumerate(plan["steps"]):
        logger.info(f"[{job_id}] Plan step {i+1}/{len(plan['steps'])}: {step_text[:80]}...")
        try:
            step_answer = await _run_agent_flow(step_text, today_str, job_id)
            step_summaries.append(f"Step {i+1}: {step_text}\n  Result: {step_answer[:300]}")
        except Exception as e:
            step_summaries.append(f"Step {i+1}: {step_text}\n  Error: {e}")

    # Phase 3: Generate final summary
    results_text = "\n".join(step_summaries)
    summary_messages = [
        {
            "role": "system",
            "content": (
                f"You are a research assistant. Today is {today_str}. "
                "Summarize what was accomplished in the completed plan. "
                "Use Markdown. Be concise."
            ),
        },
        {
            "role": "user",
            "content": f"Task: {prompt}\n\nPlan: {plan['title']}\n\nResults:\n{results_text}\n\nProvide a summary.",
        },
    ]
    llm = LLM()
    response = await llm.client.chat.completions.create(
        model=llm.model,
        messages=summary_messages,
        max_tokens=llm.max_tokens,
        stream=False,
    )
    return response.choices[0].message.content.strip()


def _format_context(results: list) -> str:
    """Format search results as context text."""
    lines = ["Search results:"]
    for i, r in enumerate(results[:5], 1):
        lines.append(f"{i}. {r.get('title', '')}")
        if r.get("description"):
            lines.append(f"   {r['description'][:200]}")
    return "\n".join(lines)
