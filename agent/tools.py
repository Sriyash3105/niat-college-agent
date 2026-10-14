import json
import os
from pathlib import Path

from tavily import TavilyClient

GROUNDING_PATH = Path(__file__).resolve().parent.parent / "data" / "niat_grounding.json"


def search_competitor_college(college_name: str) -> str:
    """Search the web for a college's syllabus and placement data and return a summary string."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    queries = [
        f"{college_name} B.Tech CSE syllabus curriculum subjects",
        f"{college_name} placements average package median salary highest package",
    ]

    sections = []
    for query in queries:
        try:
            result = client.search(
                query=query,
                search_depth="basic",  # 1 credit per search; free plan is 1,000 credits/month
                max_results=5,
                include_answer=True,
            )
        except Exception as exc:  # network / quota errors shouldn't kill the agent loop
            sections.append(f"## {query}\nSearch failed: {exc}")
            continue

        lines = [f"## {query}"]
        if result.get("answer"):
            lines.append(f"Summary: {result['answer']}")
        for item in result.get("results", []):
            snippet = (item.get("content") or "").strip().replace("\n", " ")[:600]
            lines.append(
                f"- {item.get('title', '')} ({item.get('url', '')}): {snippet}"
            )
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def get_niat_facts() -> str:
    """Return the verified NIAT grounding data as a JSON string."""
    return GROUNDING_PATH.read_text(encoding="utf-8")


# OpenAI function-calling schemas for the tools above.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_competitor_college",
            "description": (
                "Search the live web for a competitor engineering college's current "
                "syllabus/curriculum and placement statistics (average, median, highest packages)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "college_name": {
                        "type": "string",
                        "description": "Full name of the competitor college, e.g. 'Vardhaman College of Engineering, Hyderabad'.",
                    }
                },
                "required": ["college_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_niat_facts",
            "description": "Retrieve verified facts about the NIAT program (curriculum, fees, stipends, placements).",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]

TOOL_REGISTRY = {
    "search_competitor_college": search_competitor_college,
    "get_niat_facts": get_niat_facts,
}


def execute_tool(name: str, arguments: str) -> str:
    """Dispatch a tool call from the LLM and always return a string result."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"
    try:
        kwargs = json.loads(arguments) if arguments else {}
        return func(**kwargs)
    except Exception as exc:
        return f"Error running {name}: {exc}"
