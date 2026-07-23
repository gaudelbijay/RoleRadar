# Reports and Auditing

[Documentation index](document.md)

Every successful pipeline run writes two files under `reports/`.

## Markdown report

The report filename follows this pattern:

```text
report-YYYYMMDD-HHMMSS.md
```

In local Ollama mode, the synthesis prompt requests:

- An executive summary
- A section for each research angle
- Cross-cutting comparative analysis
- Conflicts and limitations
- A financial-advice disclaimer when applicable

Demo reports contain canned content and are explicitly marked as demo output.

## JSON audit trail

The audit filename follows this pattern:

```text
audit-YYYYMMDD-HHMMSS.json
```

It records:

- Original user query
- Coordinator-generated subtasks
- Agent identifiers and statuses
- Agent elapsed times
- Empty `searches` and `sources` arrays reserved for a future retrieval layer

The full prose findings are stored in the Markdown report and returned to the
calling interface, but they are not duplicated in the current audit JSON.

## Operational notes

- Timestamps use UTC.
- Filenames have one-second resolution; highly concurrent runs may need a UUID
  or higher-resolution suffix to prevent collisions.
- The current Ollama-only implementation performs no live retrieval and
  generates no citations.
- Reports reflect Gemma's existing model knowledge and should not be considered
  verified or current without independent review.
