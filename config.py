"""Central configuration for the local Ollama-backed job-summary stage."""

import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_TIMEOUT_SEC = int(os.environ.get("OLLAMA_TIMEOUT_SEC", "300"))
JOB_SUMMARY_MODEL = os.environ.get("JOB_SUMMARY_MODEL", "gemma3:4b")
JOB_SUMMARY_MAX_TOKENS = int(os.environ.get("JOB_SUMMARY_MAX_TOKENS", "900"))
