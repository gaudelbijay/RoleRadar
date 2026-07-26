"""Local LLM integration used by the optional evidence-validated Gemma summary
stage. Calls Gemma through Ollama's HTTP API.
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


def llm_complete(prompt: str, system: str = "", model: str = "", max_tokens: int = 2000) -> str:
    """Generate one completion with local Ollama."""
    return _generate(prompt, system, model or config.JOB_SUMMARY_MODEL, max_tokens)


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
