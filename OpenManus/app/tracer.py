"""
LangSmith tracing integration for LuminAgent.

Initializes LangSmith from config.toml settings and provides helpers for
wrapping the OpenAI client and tracing agent operations.

Usage:
    # In main entry point (main.py, web_server.py):
    from app.tracer import init_langsmith
    init_langsmith()  # Call once at startup

    # In agent methods — just use @traceable directly:
    from app.tracer import traceable

    @traceable(name="think", run_type="chain")
    async def think(self):
        ...

    # In llm.py — wrap the OpenAI client:
    from app.tracer import wrap_openai_client
    self.client = wrap_openai_client(AsyncOpenAI(...))

The trace hierarchy:
    BaseAgent.run → ReActAgent.step → ToolCallAgent.think / act → execute_tool
        └── All LLM API calls appear as child "llm" spans automatically
"""

import os
from typing import Optional

from app.logger import logger as loguru_logger


def init_langsmith() -> bool:
    """Initialize LangSmith tracing from config.toml settings.

    Sets the required environment variables. Must be called once at startup,
    before any tracing or LLM client wrapping occurs.

    Returns:
        True if LangSmith tracing was enabled, False otherwise.
    """
    from app.config import config

    ls_config = config.langsmith_config
    if not ls_config or not ls_config.LANGSMITH_TRACING:
        loguru_logger.info(
            "🔍 LangSmith tracing is disabled "
            "(LANGSMITH_TRACING=false or missing config)"
        )
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = ls_config.LANGSMITH_ENDPOINT
    if ls_config.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = ls_config.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = ls_config.LANGSMITH_PROJECT

    loguru_logger.info(
        f"🔍 LangSmith tracing enabled — "
        f"Project: {ls_config.LANGSMITH_PROJECT}, "
        f"Endpoint: {ls_config.LANGSMITH_ENDPOINT}"
    )
    return True


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is currently active."""
    return os.environ.get("LANGSMITH_TRACING", "").lower() == "true"


def wrap_openai_client(client):
    """Wrap an OpenAI/AsyncOpenAI client with LangSmith tracing.

    After wrapping, all calls to client.chat.completions.create() will
    automatically create child "llm" spans under any active trace context.

    When tracing is disabled, returns the client unchanged.

    Args:
        client: An OpenAI or AsyncOpenAI client instance.

    Returns:
        The wrapped (or original) client.
    """
    if not is_tracing_enabled():
        return client

    try:
        from langsmith import wrappers

        wrapped = wrappers.wrap_openai(client)
        loguru_logger.debug("✅ OpenAI client wrapped with LangSmith tracing")
        return wrapped
    except Exception as e:
        loguru_logger.warning(f"⚠️ Failed to wrap OpenAI client: {e}")
        return client


# Re-export traceable from langsmith so all call sites use a single import.
# When LANGSMITH_TRACING is not "true", langsmith.traceable is a transparent
# pass-through that adds negligible overhead (<1ms).
try:
    from langsmith import traceable  # noqa: F401
except ImportError:
    # Fallback: if langsmith is not installed, provide a no-op decorator
    def traceable(*args, **kwargs):
        """No-op traceable when langsmith is not installed."""
        if args and callable(args[0]):
            return args[0]
        return lambda f: f


# Cache the trace context manager so we don't import on every call.
_trace_cm = None


def _get_trace_cm():
    """Lazily import langsmith.trace."""
    global _trace_cm
    if _trace_cm is None:
        try:
            from langsmith import trace as _trace_cm
        except ImportError:
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _noop(*args, **kwargs):
                yield

            _trace_cm = _noop
    return _trace_cm


def trace_tool(name: str, tool_input: dict):
    """Async context manager for tracing tool executions with dynamic names.

    Usage:
        async with trace_tool(command.name, args):
            result = await tool.execute(**tool_input)
    """
    if not is_tracing_enabled():
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _noop():
            yield

        return _noop()

    return _get_trace_cm()(
        name=name,
        run_type="tool",
        metadata={"tool_input": str(tool_input)[:2000]},
    )
