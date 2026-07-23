# Project Overview

[Documentation index](document.md)

## What DeepResearch does

DeepResearch automates broad research tasks using a coordinator and several
specialized research workers:

1. The coordinator converts a user question into three to five independent
   research tasks.
2. One sub-agent is assigned to each task.
3. Sub-agents run concurrently and use local Gemma through Ollama.
4. The coordinator collects and synthesizes their findings.
5. The application saves a Markdown report and a JSON audit file.

The system can be accessed through a Gradio interface, a Streamlit interface,
or the command line.

## Example use cases

- Competitive and market landscape research
- Technology scouting
- Literature and scientific topic surveys
- Partnership and ecosystem analysis
- Historical performance and risk research
- Fact-based securities research without buy or sell recommendations

## Operating modes

### Local mode

By default, Gemma performs task decomposition, research analysis, and final
synthesis through a locally running Ollama server. No paid API key is needed.
The model has no live web access, so its output is not source-grounded.

### Demo mode

When `DEMO_MODE=1`, deterministic mock functions exercise the full pipeline
without a model. Demo output illustrates the report structure, but it is not
real research and must not be treated as factual.

## Current scope

This repository is a proof of concept. It includes parallel execution, basic
failure isolation, live UI logs, report persistence, and audit records. It does
not currently include authentication, a database, scheduled jobs, source
credibility scoring, citation verification, caching, or automated tests.
