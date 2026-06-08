INTENT_ANALYSIS_PROMPT = """\
Today's date is {current_date}. Analyze the user's question. Choose the best tool and generate appropriate parameters.

## Tool selection (CRITICAL — choose exactly ONE)
Pick the most appropriate tool for the user's request:

### "web_search" — Search the internet
Use when: real-time info, facts needing verification, weather, news, local info (attractions, restaurants, traffic, hotels), technical docs, product/company info.
NOT for: creative writing, coding, translation, opinion, math, reasoning.

### "python_execute" — Run Python code
Use when: the user asks to compute/calculate, run code, process data, do math that requires actual execution.
Generate complete, runnable Python code using print() to output results.

### "browser_use" — Browse a specific webpage
Use when: the user gives a URL and asks to extract/read its content, or asks to search-and-browse a specific site.
Supported actions: web_search, extract_content, go_to_url.

### "str_replace_editor" — Read/write/edit files
Use when: the user asks to view a file, create a file, edit file content, or replace text in a file.
Supported commands: view, create, str_replace.

### "chat" — Direct conversation, no tools needed
Use when: creative writing, opinion, reasoning, translation, coding advice (not execution), general knowledge, chitchat.

## Query rewriting rules (for web_search only)
- Convert conversational language into keyword-rich search queries.
- For time-sensitive questions: replace "今天"/"现在" with the actual date "{current_date}".
- For location questions: always include the location name.
- Remove filler words: "请问", "我想知道", "帮我查一下", "怎么样", "适合吗".
- Generate 2-3 query variants from different angles.

## Output format
Output ONLY valid JSON (no markdown wrapping, no ```json``` tags). The JSON must include:
- "tool": one of ["web_search", "python_execute", "browser_use", "str_replace_editor", "chat"]
- "reasoning": brief explanation in Chinese
- Plus tool-specific parameters:

For web_search:
{{"tool": "web_search", "search_queries": ["optimized query 1", "query 2"], "reasoning": "..."}}

For python_execute:
{{"tool": "python_execute", "python_code": "complete runnable Python code with print()", "reasoning": "..."}}

For browser_use:
{{"tool": "browser_use", "browser_action": "web_search|extract_content|go_to_url", "browser_query": "search query or extraction goal", "browser_url": "URL if go_to_url", "reasoning": "..."}}

For str_replace_editor:
{{"tool": "str_replace_editor", "file_command": "view|create|str_replace", "file_path": "/absolute/path", "file_text": "content for create", "old_str": "text to replace", "new_str": "replacement text", "reasoning": "..."}}

For chat:
{{"tool": "chat", "reasoning": "..."}}

User question: {prompt}
"""
