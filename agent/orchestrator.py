"""Runs the tool-calling loop against an OpenAI-compatible LLM and returns the parsed comparison JSON."""

import json
import os
import re
import time

from openai import APIStatusError, OpenAI

from agent.prompts import SYSTEM_PROMPT, build_user_message
from agent.tools import TOOL_SCHEMAS, execute_tool

MAX_TOOL_ROUNDS = 6
MAX_RATE_LIMIT_RETRIES = 4
REQUIRED_KEYS = ("competitor_summary", "comparison_points", "parent_script_native")

# Any OpenAI-compatible provider works; defaults to Google Gemini's free tier.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _create_with_retry(client: OpenAI, **kwargs):
    """Call the chat API, waiting out 429/503s using the provider's suggested delay."""
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except APIStatusError as exc:
            if exc.status_code not in (429, 503) or attempt == MAX_RATE_LIMIT_RETRIES:
                raise
            hint = re.search(r"retry in ([\d.]+)s", str(exc))
            delay = float(hint.group(1)) + 1 if hint else 5 * (attempt + 1)
            time.sleep(min(delay, 60))


def _parse_json(text: str | None) -> dict | None:
    """Parse a JSON object from model output, tolerating ```json fences."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_comparison_agent(college_name: str, language: str, parent_name: str | None = None) -> dict:
    # Retries are handled in _create_with_retry so blind SDK retries don't burn free-tier quota.
    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.getenv("LLM_BASE_URL", GEMINI_BASE_URL),
        max_retries=0,
    )
    model = os.getenv("LLM_MODEL", "gemini-flash-lite-latest")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(college_name, language, parent_name)},
    ]
    tools_called: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = _create_with_retry(
            client,
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.4,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            break

        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            tools_called.append(call.function.name)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": execute_tool(call.function.name, call.function.arguments),
                }
            )
    else:
        raise RuntimeError("Agent exceeded the maximum number of tool-calling rounds")

    result = _parse_json(message.content)

    # Only spend an extra request on a JSON-mode pass if the answer didn't already parse.
    if result is None or any(key not in result for key in REQUIRED_KEYS):
        messages.append(
            {"role": "user", "content": "Now return only the final JSON object as specified."}
        )
        final = _create_with_retry(
            client,
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        result = _parse_json(final.choices[0].message.content) or {}

    missing = [key for key in REQUIRED_KEYS if key not in result]
    if missing:
        raise ValueError(f"Agent response missing keys: {missing}")

    result["tools_called"] = tools_called
    return result
