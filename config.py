"""Central configuration for the multi-agent research system."""

import os

# Local Ollama models
COORDINATOR_MODEL = os.environ.get("COORDINATOR_MODEL", "gemma4")
SUBAGENT_MODEL = os.environ.get("SUBAGENT_MODEL", "gemma4")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_TIMEOUT_SEC = int(os.environ.get("OLLAMA_TIMEOUT_SEC", "300"))

# Parallelism: how many sub-agents research at the same time
MAX_PARALLEL_AGENTS = int(os.environ.get("MAX_PARALLEL_AGENTS", "4"))

# How many research subtasks the coordinator may create
MIN_SUBTASKS = 3
MAX_SUBTASKS = 5

# Token budgets
SUBAGENT_MAX_TOKENS = 2000
REPORT_MAX_TOKENS = 4000


def live_mode() -> bool:
    """Use local Ollama unless deterministic demo mode is explicitly requested."""
    return os.environ.get("DEMO_MODE", "").lower() not in {"1", "true", "yes"}
