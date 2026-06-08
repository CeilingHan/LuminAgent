"""
Standalone intent analysis function — determines which tool to use and generates
tool-specific parameters from a user's natural-language prompt.

Used by both web_server.py (tool routing) and WebSearch._analyze_search_intent
(backward compatibility for search_with_intent).
"""
import json
from datetime import datetime
from typing import Optional

from app.llm import LLM
from app.logger import logger
from app.prompt.intent_analysic import INTENT_ANALYSIS_PROMPT
from app.tracer import traceable

# Known tool names the LLM can select
KNOWN_TOOLS = {"web_search", "python_execute", "browser_use", "str_replace_editor", "chat"}


@traceable(name="intent_analysis", run_type="chain")
async def analyze_intent(
    prompt: str,
    current_date: Optional[str] = None,
) -> dict:
    """Analyze user intent and decide which tool to use with what parameters.

    Args:
        prompt: The raw user question (any language).
        current_date: Date string like "2026年06月05日". Auto-generated if None.

    Returns:
        dict with at minimum:
            tool: str          — one of KNOWN_TOOLS
            reasoning: str     — brief explanation in Chinese

        Plus tool-specific keys:
            web_search:     search_queries: list[str]
            python_execute: python_code: str
            browser_use:    browser_action: str, browser_query: str, browser_url: str (optional)
            str_replace_editor: file_command: str, file_path: str, file_text: str (optional),
                                old_str: str (optional), new_str: str (optional)
            chat:           (no extra keys)
    """
    if current_date is None:
        current_date = datetime.now().strftime("%Y年%m月%d日")

    try:
        llm = LLM()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an intent analyzer for a multi-tool AI assistant. "
                    "Analyze the user's question, decide which tool to use, and generate "
                    "the appropriate parameters. Output ONLY valid JSON, no markdown wrapping."
                ),
            },
            {
                "role": "user",
                "content": INTENT_ANALYSIS_PROMPT.format(
                    prompt=prompt,
                    current_date=current_date,
                ),
            },
        ]
        response = await llm.client.chat.completions.create(
            model=llm.model,
            messages=messages,
            max_tokens=500,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove opening ```json or ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        result = json.loads(raw)
        tool = result.get("tool", "chat")

        # Normalize: ensure tool is one we recognize
        if tool not in KNOWN_TOOLS:
            logger.warning(
                f"Unknown tool '{tool}' from intent analysis, falling back to chat"
            )
            tool = "chat"

        # Build normalized output
        normalized: dict = {
            "tool": tool,
            "reasoning": result.get("reasoning", ""),
        }

        # Extract tool-specific parameters
        if tool == "web_search":
            normalized["search_queries"] = result.get("search_queries", [prompt])
        elif tool == "python_execute":
            normalized["python_code"] = result.get("python_code", "")
        elif tool == "browser_use":
            normalized["browser_action"] = result.get("browser_action", "web_search")
            normalized["browser_query"] = result.get("browser_query", prompt)
            normalized["browser_url"] = result.get("browser_url", "")
        elif tool == "str_replace_editor":
            normalized["file_command"] = result.get("file_command", "view")
            normalized["file_path"] = result.get("file_path", "")
            normalized["file_text"] = result.get("file_text", "")
            normalized["old_str"] = result.get("old_str", "")
            normalized["new_str"] = result.get("new_str", "")
        # chat → no extra params needed

        logger.info(f"Intent analysis: tool={tool}, reasoning={normalized.get('reasoning', '')[:80]}")
        return normalized

    except json.JSONDecodeError as e:
        logger.warning(f"Intent analysis JSON parse failed: {e}, raw={raw[:200]}")
        return {"tool": "chat", "reasoning": "JSON parse failed, falling back to chat"}

    except Exception as e:
        logger.warning(f"Intent analysis failed: {e}, falling back to chat")
        return {"tool": "chat", "reasoning": f"analysis failed: {str(e)}"}
