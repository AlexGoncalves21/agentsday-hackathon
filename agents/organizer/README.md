# Organizer

The Organizer reads enriched Markdown files from the shared `input/` directory and compiles them into the shared `brain/` directory.

In dev mode, it rebuilds `brain/` from scratch on every run and writes a fresh `runs/latest_report.md`.

Run from the repo root:

```bash
python3 -m agents.organizer.second_brain_agent validate-inputs
python3 -m agents.organizer.second_brain_agent run
```
