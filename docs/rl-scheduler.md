# Adaptive source scheduling and reinforcement learning

[Documentation index](document.md) · [Technical report](../technical_report.md)

For the full mathematical derivation—including the MDP and semi-MDP model, state discretization, Bellman equations, reward function, Q-learning update, convergence assumptions, and numerical examples—read [Mathematics of the RL source scheduler](rl-mathematics.md).

## Executive summary

Job Search uses an adaptive controller to decide whether another wave of job-source agents should run or whether the current verified result set is sufficient.

The implementation is **RL-capable**, but the repository does not ship a trained policy. This distinction is essential:

| Runtime condition | Controller actually used |
|---|---|
| No policy file configured | Deterministic adaptive stopping rules |
| Policy path missing | Deterministic adaptive stopping rules |
| Policy malformed or unsupported | Logged fallback to deterministic rules |
| Valid policy with learned Q-values | Tabular Q-learning inference, with deterministic safety overrides |

The normal audit currently reports `policy_loaded: false`, which means the default experience uses the safe deterministic controller inside the RL scheduling framework. It must not be described as trained or self-optimizing until a learned policy passes the promotion gates described below.

## Why scheduling exists

Running every source on every search maximizes coverage, but it can waste network calls and processing when the first high-value sources already provide enough verified jobs. Scheduling attempts to reduce that unnecessary work while preserving the same final results.

The controller answers one bounded question after each completed wave:

```text
Do we launch another source wave, or stop launching new sources?
```

It does not decide whether a job is eligible, how a job is ranked, or whether an application is prepared.

## End-to-end flow

```text
User search settings
        │
        ▼
Build the finite source list
        │
        ▼
Prioritize the major-site adapter for the initial job-search wave
        │
        ▼
Launch a bounded wave of source agents
        │
        ▼
Wait for the entire wave to finish
        │
        ▼
Run deterministic job eligibility gates on the accumulated listings
        │
        ▼
Build a non-sensitive SearchState
        │
        ▼
QLearningPolicy.choose(state, explore=False)
        │
        ├── unseen state / no policy ──► deterministic fallback
        │
        ├── launch_next ──────────────► launch another bounded wave
        │
        └── stop_launching ───────────► rank and present accumulated jobs
```

Decisions occur only at wave boundaries. A fast source cannot trigger another launch while its existing wave partners are still running.

## Code organization

All scheduling and learning code is isolated in `rl_scheduler/`.

| Module | Responsibility |
|---|---|
| `models.py` | Policy actions, validated scheduler configuration, and non-sensitive state |
| `policy.py` | Q-table loading, saving, inference, updates, deterministic fallback, and reward calculation |
| `runner.py` | Bounded live source waves, policy decisions, timing, and audit traces |
| `train.py` | Explicit offline Q-learning from versioned transitions |
| `replay.py` | Privacy-bounded source recording and deterministic scenario loading |
| `evaluate.py` | Paired policy replay, ranking metrics, aggregation, and promotion gates |

`core/jobs.py` remains responsible for source definitions, eligibility gates, ranking, and the final result schema. The scheduler cannot bypass it.

## Policy state

`SearchState` contains seven operational values:

| Field | Meaning |
|---|---|
| `elapsed_seconds` | Time since source scheduling started |
| `fetched_jobs` | Listings collected before final ranking |
| `eligible_jobs` | Listings currently passing every mandatory job gate |
| `completed_agents` | Finished source agents, including failures |
| `failed_agents` | Source agents that raised errors |
| `active_agents` | Source agents still running |
| `remaining_agents` | Sources not yet launched |

The state never contains:

- raw CV text;
- applicant name, email, phone number, or profile answers;
- portfolio page text;
- credentials, cookies, or access tokens;
- raw job descriptions.

### State bucketing

Tabular Q-learning needs a finite state space. `SearchState.bucket()` converts continuous and large counters into a compact key:

```text
t{elapsed bucket}|e{eligible bucket}|r{remaining}|f{failures}|a{active}
```

The current discretization is:

```text
elapsed bucket  = min(5, floor(elapsed_seconds / 3))
eligible bucket = min(5, floor(eligible_jobs / 3))
remaining       = min(5, remaining_agents)
failures        = min(2, failed_agents)
active          = min(3, active_agents)
```

`fetched_jobs` and `completed_agents` remain visible in traces but do not affect the current Q-table key.

## Action space

The policy has only two actions:

| Action | Effect |
|---|---|
| `launch_next` | Fill another wave up to `max_parallel_agents` |
| `stop_launching` | Stop adding sources and continue to final ranking |

The current policy does **not** choose a source by name. Source priority is deterministic. A future contextual policy may add source-specific actions, but that behavior is not implemented and is not claimed here.

## Deterministic cold-start policy

When a state has no learned Q-values, the controller uses these rules in order:

1. Stop if no source remains.
2. Stop if `eligible_jobs >= target_results`.
3. Stop if the soft deadline has passed and `eligible_jobs >= minimum_results`.
4. Stop if the hard deadline has passed and `eligible_jobs >= minimum_results`.
5. Otherwise, launch another wave.

The deadline conditions deliberately require the minimum result floor. The scheduler cannot stop with zero verified jobs merely because time elapsed. If verified yield remains below the minimum, it exhausts the finite remaining source list.

This protection was added after a real failure where generic feeds produced zero matches and the broad major-site adapter was skipped. The major-site adapter is now included in the initial job-search wave, and a permanent regression test protects the zero-result fallback.

## Q-learning policy

For a trained policy, the action value is learned with the standard tabular update:

```text
Q(s, a) ← Q(s, a) + α [r + γ maxₐ′ Q(s′, a′) − Q(s, a)]
```

Default learning parameters:

| Parameter | Default | Meaning |
|---|---:|---|
| `α` | `0.20` | Learning rate |
| `γ` | `0.90` | Future-reward discount |
| `ε` | `0.00` | Exploration probability at normal construction |

Live searches always call:

```python
policy.choose(state, config, explore=False)
```

They never call `update()` and never explore. Learning occurs only through the explicit offline trainer.

### Reward function

The provided transition reward is:

```text
reward = 2.00 × max(0, change in verified jobs)
       − 0.05 × incremental elapsed seconds
       − 0.20 × source launched
       − 1.00 × source failure
```

In symbolic form:

```text
rₜ = wᵧ ΔYₜ − wₗ ΔTₜ − w꜀ Cₜ − wꜰ Fₜ
```

where `ΔYₜ` is newly verified yield, `ΔTₜ` is incremental time, `Cₜ` indicates an added source call, and `Fₜ` indicates a failed source.

The reward does not use raw fetched-job count because a noisy source should not be rewarded for returning irrelevant volume.

## Safety boundary

The policy cannot change or override:

- country matching;
- maximum posting age;
- job versus internship classification;
- education requirements;
- salary requirements;
- robotics and other domain evidence;
- URL and network-safety rules;
- resume privacy rules;
- ranking algorithms;
- application preparation or submission behavior.

Mandatory gates run in `core/jobs.py`. A high Q-value cannot admit a rejected listing.

Additional safeguards include:

- validated initial and maximum agent counts;
- bounded finite source lists;
- no live exploration;
- deterministic fallback for missing or malformed policies;
- complete-wave decisions;
- cached eligibility evaluation per accumulated batch;
- zero-result coverage protection;
- allowed completion of already-running calls to avoid leaked workers.

## Runtime configuration

The scheduler is enabled by default in Gradio, Streamlit, CLI, and direct searches.

Disable it in a dashboard by clearing **Optimize source agents with RL scheduler**, or use:

```bash
./run.sh cli --country "United States" \
  --no-rl-scheduler "robotics engineer"
```

| Variable | Default | Purpose |
|---|---:|---|
| `JOBSEARCH_SOURCE_SCHEDULER` | `rl` | Direct-core mode; use `all` for full dispatch |
| `JOBSEARCH_RL_POLICY_PATH` | empty | Optional version-1 Q-policy JSON |
| `JOBSEARCH_RL_INITIAL_AGENTS` | `2` | Initial wave size |
| `JOBSEARCH_RL_MAX_PARALLEL` | `2` | Maximum agents in a wave |
| `JOBSEARCH_RL_MIN_RESULTS` | `5` | Minimum result floor for deadline stopping |
| `JOBSEARCH_RL_TARGET_RESULTS` | `15` | Immediate stopping target |
| `JOBSEARCH_RL_SOFT_DEADLINE` | `6` | Soft stopping threshold in seconds |
| `JOBSEARCH_RL_HARD_DEADLINE` | `15` | Strong stopping threshold, subject to the result floor |
| `JOBSEARCH_RECORD_SCENARIO_PATH` | empty | Optional sanitized replay destination |

## Offline training

Training input uses a versioned JSON envelope:

```json
{
  "version": 1,
  "transitions": [
    {
      "state": {
        "elapsed_seconds": 4.2,
        "fetched_jobs": 80,
        "eligible_jobs": 7,
        "completed_agents": 2,
        "failed_agents": 0,
        "active_agents": 0,
        "remaining_agents": 3
      },
      "action": "launch_next",
      "reward": 8.4,
      "next_state": {
        "elapsed_seconds": 7.1,
        "fetched_jobs": 130,
        "eligible_jobs": 12,
        "completed_agents": 3,
        "failed_agents": 0,
        "active_agents": 0,
        "remaining_agents": 2
      },
      "terminal": false
    }
  ]
}
```

Train and save a policy:

```bash
python -m rl_scheduler.train \
  transitions.json scheduler-policy.json --epochs 20
```

Use it during a search:

```bash
JOBSEARCH_RL_POLICY_PATH=scheduler-policy.json ./run.sh gradio
```

Policy format:

```json
{
  "version": 1,
  "q_values": {
    "t1|e2|r3|f0|a0": {
      "launch_next": 3.7,
      "stop_launching": 1.4
    }
  }
}
```

The audit must report `policy_loaded: true` before a run is described as trained RL.

## Recording and replay

Two separate live searches are not a fair policy comparison because source contents and rate limits can change. The project records every source once and replays each policy against identical batches.

### 1. Record every source

```bash
./run.sh cli --country "United States" --no-rl-scheduler \
  --record-scenario benchmarks/replays/scenario.json "QUERY"
```

Full dispatch is required during recording so every candidate policy can access every source.

Recorded fields include:

- query and non-sensitive search settings;
- source name;
- source elapsed time;
- source error text;
- normalized public job evidence.

The sanitizer removes internal fields, applicant data, CV content, emails, phone numbers, and credentials. Raw replay files are ignored by Git because they contain copied public job descriptions.

### 2. Generate a relevance-label template

```bash
PYTHONPATH=. .venv/bin/python -m rl_scheduler.evaluate \
  benchmarks/replays/scenario.json \
  --label-template benchmarks/replays/labels.json \
  --output benchmarks/replays/evaluation.json
```

Assign each job a grade:

| Grade | Interpretation |
|---:|---|
| `0` | Irrelevant or unacceptable |
| `1` | Weak match |
| `2` | Good match |
| `3` | Excellent match |

### 3. Evaluate with labels

```bash
PYTHONPATH=. .venv/bin/python -m rl_scheduler.evaluate \
  benchmarks/replays/scenario.json \
  --labels benchmarks/replays/labels.json \
  --policy scheduler-policy.json \
  --output benchmarks/replays/evaluation.json
```

The evaluator compares:

1. full parallel dispatch;
2. deterministic adaptive scheduling;
3. trained RL, only when a non-empty policy is loaded.

## Metrics and promotion gates

The paired evaluator reports:

- modeled p50 and p95 latency;
- mean source calls;
- mean verified jobs;
- empty-result rate;
- unique companies;
- Precision@5;
- Precision@10;
- Recall@50;
- NDCG@10.

A candidate passes only when all applicable checks succeed:

| Gate | Required threshold |
|---|---:|
| p50 latency | At least 20% lower than full parallel |
| Mean source calls | At least 25% lower |
| Empty-result rate | No worse than full parallel |
| NDCG@10 | No more than 0.01 below baseline |
| Recall@50 | No more than 0.02 below baseline |
| Labels | Must be available |

Missing labels automatically fail promotion. A fast policy is not accepted if result quality is unknown.

## Current measured evidence

### Synthetic timing benchmark

Ten controlled trials produced:

| Scenario | Latency change | Source-call change |
|---|---:|---:|
| Initial wave reaches the target | **−46.42%** | **−60.0%** |
| Initial wave has no eligible jobs | **+125.84%** | **0.0%** |

This demonstrates both the possible benefit and the sparse-query risk of adaptive waves.

### Real paired replay

For `computer vision robotics research engineer` with United States, PhD, 10 days, and a 100,000 salary minimum:

| Metric | Full parallel | Adaptive |
|---|---:|---:|
| Source calls | 5 | **2** |
| Fetched listings | 302 | **164** |
| Verified jobs | 12 | 12 |
| Unique companies | 10 | 10 |
| Modeled latency | 96.4108 s | 96.4108 s |
| Ranked list | 12 jobs | Identical 12 jobs |

The adaptive controller reduced calls by 60% and fetched volume by 45.7% while preserving the identical ranked list in this scenario. It did not improve latency because the required major-site adapter dominated the critical path.

## What can be claimed today

Accurate:

> Adaptive scheduling reduced source calls by 60% while preserving the identical ranked result list in one controlled real-query replay.

Not yet accurate:

> Reinforcement learning has optimized job search.

That stronger statement requires:

- multiple diverse recorded and labeled scenarios;
- a non-empty trained policy;
- `policy_loaded: true` during evaluation;
- trained-policy performance above deterministic adaptive scheduling;
- every promotion gate passing.

## Audit fields

Every adaptive search adds:

```json
{
  "source_scheduler": {
    "mode": "rl",
    "launched_agents": 2,
    "skipped_agents": 3,
    "elapsed_seconds": 65.7952,
    "policy_loaded": false
  },
  "scheduler_trace": [
    {
      "event": "decision",
      "action": "stop_launching",
      "state": {
        "elapsed_seconds": 65.7952,
        "fetched_jobs": 161,
        "eligible_jobs": 12,
        "completed_agents": 2,
        "failed_agents": 0,
        "active_agents": 0,
        "remaining_agents": 3
      }
    }
  ]
}
```

These fields explain why the controller stopped and whether a trained policy participated.

## Operational checklist

Before calling a policy optimized:

- [ ] Record complete all-source scenarios.
- [ ] Cover multiple roles, countries, education levels, salary settings, jobs, and internships.
- [ ] Label relevance from 0–3.
- [ ] Split training and evaluation scenarios.
- [ ] Train a non-empty versioned Q-policy.
- [ ] Verify `policy_loaded: true`.
- [ ] Run paired replay against identical source batches.
- [ ] Confirm zero hard-filter violations.
- [ ] Confirm empty-result rate does not increase.
- [ ] Pass latency, source-call, NDCG, and recall gates.
- [ ] Keep full dispatch available as a fallback.
