# Usage

[Documentation index](document.md)

DeepResearch provides three interfaces over the same coordinator pipeline.

## One-command launcher

The launcher creates `.venv` when needed, installs Python dependencies, starts
Ollama when necessary, ensures Gemma 4 is available, and opens the selected UI:

```bash
./run.sh
```

Gradio is the default. To start Streamlit instead:

```bash
./run.sh streamlit
```

## Gradio

Gradio is the recommended interface:

```bash
python app_gradio.py
```

Open `http://127.0.0.1:7860`, enter a research question, and select **Run
research**. The activity panel streams coordinator and agent progress while the
report is being produced.

## Streamlit

```bash
streamlit run app_streamlit.py
```

The Streamlit interface displays live activity, renders the report, and offers
a Markdown download button.

## Command line

```bash
python cli.py "Your research question"
```

If no question is provided, the CLI uses its built-in semiconductor example:

```bash
python cli.py
```

Depending on the local Python setup, the executable may be named `python3`.

## Writing effective queries

Include the subject, desired research angles, time period, and comparison
criteria. For example:

```text
Compare leading solid-state battery developers, their technical approaches,
major partnerships, commercialization milestones since 2022, and key risks.
```

Broad but explicit questions give the coordinator enough freedom to create
independent tasks while preserving the user's priorities.

## Financial topics

Prompts and reports enforce a factual-research boundary for investments and
securities. The system can discuss historical performance, fundamentals,
partnerships, and risks, but it is not intended to provide personalized
financial advice or buy/sell recommendations.
