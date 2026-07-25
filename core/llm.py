"""Local LLM integration and deterministic demo responses.

Local mode calls Gemma through Ollama's HTTP API. Ollama does not include a
web-search provider, so the current sub-agents use model knowledge rather than
live sources. Demo mode uses deterministic placeholders and requires no model.
"""

from __future__ import annotations

import json
from urllib import error, request

import config


def _generate(prompt: str, system: str, model: str, max_tokens: int) -> str:
    """Call Ollama's non-streaming generate endpoint."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }).encode("utf-8")
    req = request.Request(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=config.OLLAMA_TIMEOUT_SEC) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Cannot connect to Ollama at {config.OLLAMA_BASE_URL}. "
            f"Start Ollama and run `ollama pull {model}`."
        ) from exc

    text = body.get("response")
    if not isinstance(text, str):
        raise RuntimeError("Ollama response did not contain generated text.")
    return text


def llm_complete(
    prompt: str,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 2000,
) -> str:
    """Generate coordinator output with local Ollama."""
    return _generate(
        prompt, system, model or config.COORDINATOR_MODEL, max_tokens
    )


def llm_research(
    prompt: str,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 2000,
) -> dict:
    """Generate sub-agent findings with Gemma.

    Provenance arrays remain empty because Ollama has no built-in web search.
    """
    text = _generate(prompt, system, model or config.SUBAGENT_MODEL, max_tokens)
    return {"text": text, "sources": [], "searches": []}


def mock_decompose(query: str) -> list[dict]:
    return [
        {
            "title": "Landscape & key players",
            "task": f"Identify the main companies/entities relevant to: {query}. "
                    "List leaders, challengers, and what differentiates them.",
        },
        {
            "title": "Historical performance (5 years)",
            "task": f"Research 5-year performance/track record relevant to: {query}. "
                    "Trends, growth, notable inflection points.",
        },
        {
            "title": "Partnerships & collaborations",
            "task": f"Find collaborations, partnerships, supply relationships, and "
                    f"ecosystem position relevant to: {query}.",
        },
        {
            "title": "Risks & recent developments",
            "task": f"Investigate risks, controversies, and recent developments "
                    f"relevant to: {query}.",
        },
    ]


def mock_research(subtask: dict, query: str) -> dict:
    text = (
        f"[DEMO MODE — canned findings]\n"
        f"Subtask: {subtask['title']}\n\n"
        f"In local mode, this sub-agent would ask Gemma through Ollama to "
        f"analyze: \"{subtask['task']}\".\n\n"
        f"Example output would contain organized analysis related to the user "
        f"query: \"{query}\"."
    )
    return {"text": text, "sources": [], "searches": []}


def mock_report(query: str, findings: list[dict]) -> str:
    sections = "\n\n".join(
        f"## {f['subtask']['title']}\n\n{f['result']['text']}" for f in findings
    )
    return (
        f"# Research Report (Demo Mode)\n\n**Query:** {query}\n\n"
        f"{sections}\n\n---\n*Start Ollama with Gemma and unset DEMO_MODE "
        f"to generate a local model-synthesized report.*"
    )


def parse_json_block(raw: str):
    """Parse JSON out of an LLM response, stripping code fences if present."""
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    starts = [position for position in (cleaned.find("{"), cleaned.find("["))
              if position >= 0]
    start = min(starts) if starts else -1
    candidate = cleaned[start:] if start != -1 else cleaned
    # Gemma may add an explanation after valid JSON. raw_decode accepts the
    # first complete JSON value instead of rejecting the trailing text.
    value, _ = json.JSONDecoder().raw_decode(candidate)
    return value
