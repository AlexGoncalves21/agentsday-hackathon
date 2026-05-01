from __future__ import annotations

import os
from pathlib import Path

from agents.organizer.second_brain_agent.env import load_dotenv

from .models import ResearchConfig


def load_research_config(workspace: Path) -> ResearchConfig:
    load_dotenv(workspace / ".env")
    _mirror_langsmith_env()
    return ResearchConfig(
        input_dir=workspace / "input",
        runs_dir=workspace / "runs",
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        apify_api_token=os.environ.get("APIFY_API_TOKEN", ""),
        timeout_seconds=int(os.environ.get("RESEARCHER_TIMEOUT_SECONDS", "180")),
        langsmith_tracing=_env_truthy(os.environ.get("LANGSMITH_TRACING")),
        langsmith_project=os.environ.get("LANGSMITH_PROJECT", "agentsday"),
    )


def _mirror_langsmith_env() -> None:
    pairs = {
        "LANGCHAIN_API_KEY": "LANGSMITH_API_KEY",
        "LANGCHAIN_TRACING_V2": "LANGSMITH_TRACING",
        "LANGCHAIN_PROJECT": "LANGSMITH_PROJECT",
        "LANGCHAIN_ENDPOINT": "LANGSMITH_ENDPOINT",
    }
    for target, source in pairs.items():
        if source in os.environ and target not in os.environ:
            os.environ[target] = os.environ[source]


def _env_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

