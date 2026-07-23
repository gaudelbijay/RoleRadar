# Multi-Agent Deep Research System
### AI Agent Automation Project — Proposal & Technical Design

---

## 1. Project Concept

**DeepResearch** is a multi-agent AI automation system that answers open-ended
questions by dividing the work among cooperating local agents. A **coordinator
(principal) agent** decomposes the user's query into independent subtasks; a
pool of Gemma **sub-agents** analyzes those subtasks **in parallel** through
Ollama; the sub-agents submit structured findings back to the coordinator,
which **synthesizes a final report** with cross-cutting comparative analysis.
The system includes Gradio and Streamlit web interfaces.

Example: given *"Research silicon-based semiconductor companies: 5-year
performance, collaborations, risks"*, the coordinator spawns sub-agents for
the industry landscape, historical performance, partnerships, and risks; each
analyzes its angle independently with Gemma; the coordinator merges everything
into one comparative report. For investment-related queries the system avoids
buy/sell recommendations and personalized financial advice.

## 2. Business Problem

Broad analysis often spans several distinct angles. Done in one sequential
conversation, breadth competes with depth. This project demonstrates how to
**parallelize that work**: split a complex question into independent
workstreams, execute them concurrently with local models, and integrate the
results into a coherent deliverable. Because the current implementation has no
retrieval layer, it demonstrates analysis orchestration rather than verified
deep web research.

## 3. Objectives

1. Decompose any research query into 3–5 independent, parallelizable subtasks automatically.
2. Execute all subtasks concurrently with local Gemma sub-agents.
3. Produce a synthesized report with an executive summary, per-angle sections,
   cross-section comparative analysis, and honest limitations.
4. Provide a usable web UI (Gradio + Streamlit) with live agent-activity streaming.
5. Log subtasks, agent status, and timing for each run.

## 4. Multi-Agent Architecture

```
                         ┌────────────────────────┐
        user query  ───► │  UI (Gradio/Streamlit) │
                         └───────────┬────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │   COORDINATOR (principal)     │
                     │  1. decompose query → tasks   │
                     │  2. dispatch sub-agents       │
                     │  3. collect findings          │
                     │  4. synthesize final report   │
                     └──┬─────────┬─────────┬────────┘
                        ▼         ▼         ▼        (parallel, ThreadPoolExecutor)
                  ┌─────────┐┌─────────┐┌─────────┐
                  │ SUB-    ││ SUB-    ││ SUB-    │   ... up to MAX_SUBTASKS
                  │ AGENT 1 ││ AGENT 2 ││ AGENT N │
                  │ local   ││ local   ││ local   │   each: analyze its assigned
                  │ Gemma   ││ Gemma   ││ Gemma   │   angle with Ollama
                  │ analyze ││ analyze ││ analyze │
                  └────┬────┘└────┬────┘└────┬────┘
                       └──────────┼──────────┘
                                  ▼
                    findings envelopes {text, status,
                    timing; reserved provenance fields}
                                  ▼
                  ┌───────────────────────────────┐
                  │  FINAL REPORT (markdown)      │
                  │  + audit JSON                  │
                  └───────────────────────────────┘
```

**Design decisions and why:**

- **Star topology (sub-agents talk only to the coordinator).** Peer-to-peer agent chatter is hard to debug and rarely helps for research decomposition. The star keeps subtasks independent — which is exactly what makes them parallelizable.
- **Coordinator never performs subtask analysis.** The coordinator owns planning
  and synthesis; sub-agents own the independent analysis. Only the coordinator
  sees all findings, enabling cross-cutting comparison.
- **Parallelism via `ThreadPoolExecutor`.** Ollama calls are I/O-bound from the
  Python application's perspective. `MAX_PARALLEL_AGENTS` caps concurrency to
  control local CPU, GPU, and memory pressure.
- **Local inference.** Coordinator and sub-agents use Gemma through Ollama, so
  no paid model API key is required.
- **Graceful degradation.** One failed sub-agent doesn't kill the run; its error is recorded and the coordinator synthesizes from whatever succeeded, noting the gap.
- **Dual mode.** Local mode uses Gemma through Ollama. Setting `DEMO_MODE=1`
  selects deterministic mock responses so the full pipeline remains testable
  without a running model.

## 5. Agent Specifications

**Coordinator (principal) agent**
- *Decompose:* LLM call producing a strict JSON array of `{title, task}` subtasks; falls back to a sensible default plan if parsing fails.
- *Dispatch/collect:* thread pool; findings collected as futures complete, then re-ordered for a stable report.
- *Synthesize:* LLM call over the full findings bundle with a system prompt requiring executive summary, per-section synthesis, a comparative-analysis section, limitations, and (for securities queries) a no-financial-advice boundary.

**Research sub-agent**
- Receives one subtask brief plus the overall query for context.
- Uses local Gemma inference through Ollama. The current implementation has no
  web-search or retrieval layer and therefore does not produce verified sources.
- The system prompt forbids claims of live access or invented citations and
  asks agents to state uncertainty explicitly.
- Returns a structured envelope: `{text, sources[], searches[], status, elapsed}`.

## 6. Technology Stack

- **Python 3.11+**, standard library `concurrent.futures` for parallelism
- **Ollama + Gemma** — local coordinator reasoning, sub-agent analysis, and
  report synthesis
- **Gradio** — primary UI with live streaming of agent activity
- **Streamlit** — alternative UI implementation of the same backend
- **Markdown + JSON artifacts** — reports and audit trails in `reports/`

## 7. Evaluation & Success Metrics

| Metric | Method | Target |
|---|---|---|
| Decomposition quality | Human rating: subtasks independent, complementary, complete | ≥ 4/5 avg |
| Factual caution | Human review of uncertainty and unsupported-current-claim handling | ≥ 4/5 avg |
| Coverage | % of key facets (from an expert checklist) present in report | ≥ 80% |
| Wall-clock speedup | Parallel run vs forcing sequential (MAX_PARALLEL_AGENTS=1) | ≥ 2.5× |
| Robustness | Runs completing despite 1 injected sub-agent failure | 100% |

## 8. Roadmap

**Phase 1 — Core system (done, this repo):** coordinator, parallel local Gemma
sub-agents, synthesis, Gradio + Streamlit UIs, CLI, audit logging, and demo mode.

**Phase 2 — Depth (2–3 weeks):** iterative coordination (coordinator reviews findings and can dispatch follow-up sub-agents for gaps), per-source credibility scoring, structured data extraction (tables of figures), PDF/report export.

**Phase 3 — Specialization (3–4 weeks):** domain-specific sub-agent types (financial-data agent using market-data APIs, academic agent using arXiv/Semantic Scholar, news agent), caching layer, cost dashboard.

**Phase 4 — Productization (4 weeks):** user accounts, saved reports, scheduled recurring research runs, evaluation harness with golden queries.

## 9. Risks & Mitigations

- **Hallucinated or ungrounded claims** → prompts forbid invented citations and
  require limitations to be stated. A retrieval layer is still needed before
  the system can support source-grounded or current factual research.
- **Latency or resource blowups** → hard caps on subtask count, token budgets,
  and parallelism.
- **Misuse as financial advice** → explicit system-prompt boundary: factual research and evaluation frameworks only, no buy/sell recommendations, disclaimer appended to securities-related reports.
- **Rate limits / partial failures** → per-agent try/except with error envelopes; the run always completes and reports what failed.

## 10. Repository Layout

```
deep-research/
├── PROJECT.md            ← this document
├── README.md             ← setup & usage
├── requirements.txt
├── config.py             ← models, parallelism, budgets, mode detection
├── cli.py                ← terminal runner
├── app_gradio.py         ← Gradio UI (live log streaming)
├── app_streamlit.py      ← Streamlit UI
├── agents/
│   ├── coordinator.py    ← principal agent: decompose/dispatch/synthesize
│   └── subagent.py       ← autonomous parallel research worker
├── core/
│   └── llm.py            ← Ollama/Gemma calls and offline mocks
└── reports/              ← generated reports + audit JSON per run
```
