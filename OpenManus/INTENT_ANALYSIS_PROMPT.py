INTENT_ANALYSIS_PROMPT = """Classify whether web search is required.

Criteria:

SEARCH:

* Time-sensitive information
* External facts needing verification
* Documentation, APIs, libraries
* Products, companies, pricing
* News, events, trends

NO_SEARCH:

* Writing
* Coding
* Translation
* Math
* Reasoning
* General explanations
* Summarization

Output JSON only:
{
  "intent": "knowledge|coding|writing|search|math|translation",
  "should_search": true,
  "search_queries": [],
  "reasoning": ""
}
Question:
{prompt}
"""