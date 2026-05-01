from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class TraceRecorder:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self.trace_path = runs_dir / "trace.jsonl"
        self.subagents_dir = runs_dir / "subagents"
        self._subagent_notes: Dict[str, List[str]] = {}

    def reset(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.subagents_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path.write_text("")
        for path in self.subagents_dir.glob("*.md"):
            path.unlink()
        self._subagent_notes = {}

    def event(self, phase: str, message: str, **data: Any) -> None:
        payload = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "phase": phase,
            "message": message,
            "data": data,
        }
        with self.trace_path.open("a") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def subagent(self, name: str, note: str) -> None:
        self._subagent_notes.setdefault(name, []).append(note)
        self.event(f"subagent:{name}", note)

    def flush_subagents(self) -> None:
        for name, notes in sorted(self._subagent_notes.items()):
            lines = [f"# {name.title()} Trace", ""]
            lines.extend(f"- {note}" for note in notes)
            (self.subagents_dir / f"{name}.md").write_text("\n".join(lines).rstrip() + "\n")

