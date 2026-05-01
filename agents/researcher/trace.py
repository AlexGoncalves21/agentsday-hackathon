from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class ResearchTraceRecorder:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self.trace_path = runs_dir / "researcher_trace.jsonl"

    def event(self, phase: str, message: str, **data: Any) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "phase": phase,
            "message": message,
            "data": data,
        }
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

