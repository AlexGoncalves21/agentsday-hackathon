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

The deterministic Organizer path works with the local Python used during development. The LLM-backed Deep Agents path requires Python 3.11+ because the `deepagents` package requires Python 3.11 or newer.

Observe the run:

- `runs/latest_report.md` summarizes inputs, pages, quality checks, and trace paths.
- `runs/trace.jsonl` records phase-by-phase structured events.
- `runs/subagents/*.md` contains human-readable notes for the curator, synthesizer, critic, and archivist passes.
- `brain/index.md` is generated at the end and links the compiled Markdown set.
- `brain/graph.json` and `brain/graph_diff.json` are generated deterministically after Markdown writing finishes.

The deterministic compiler does not expose hidden model reasoning. It records observable decisions and outputs so the run can be debugged without relying on private chain-of-thought.

Graph generation lives in `agents/organizer/second_brain_agent/graph.py`. It creates one node per Markdown file, extracts internal Markdown and wiki-style links, and records new or changed nodes by comparing the current graph to the previous graph state.
