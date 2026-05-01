# Organizer

The Organizer reads enriched Markdown files from the shared `input/` directory and compiles them into the shared `brain/` directory.

In dev mode, it rebuilds `brain/` from scratch on every run and writes a fresh `runs/latest_report.md`.

Run from the repo root:

```bash
python3 -m agents.organizer.second_brain_agent validate-inputs
python3 -m agents.organizer.second_brain_agent run
```

Check available Gemini models for the current `GEMINI_API_KEY`:

```bash
python3 -m agents.organizer.second_brain_agent list-models
```

Organizer runs use the LLM-backed reasoning critic by default. Use a Python 3.11+ environment with the project dependencies installed (`python3 -m pip install -e .`) and LangSmith/Gemini environment variables set. For local tests or offline debugging, pass `--deterministic` to skip model reasoning.

Observe the run:

- `runs/latest_report.md` summarizes inputs, pages, quality checks, and trace paths.
- `runs/trace.jsonl` records phase-by-phase structured events.
- `runs/subagents/*.md` contains human-readable notes for the curator, synthesizer, critic, and archivist passes.
- `brain/index.md` is generated at the end and links the compiled Markdown set.
- `brain/graph.json` and `brain/graph_diff.json` are generated deterministically after Markdown writing finishes.

The compiler does not expose hidden model reasoning. It records observable decisions and model critique summaries so the run can be debugged without relying on private chain-of-thought. LangSmith traces are emitted for the model-backed critic when tracing is enabled.

Graph generation lives in `agents/organizer/second_brain_agent/graph.py`. The Organizer passes semantic TF-IDF links to it so compiled notes can stay free of generated `Related` sections, and the graph records new or changed nodes by comparing the current graph to the previous graph state.
