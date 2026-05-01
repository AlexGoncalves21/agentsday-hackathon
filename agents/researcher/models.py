from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


SubmissionType = Literal["x_url", "web_url", "question", "topic_or_concept", "note"]


@dataclass(frozen=True)
class ResearchConfig:
    input_dir: Path
    runs_dir: Path
    brain_dir: Path
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    apify_api_token: str = ""
    timeout_seconds: int = 180
    langsmith_tracing: bool = False
    langsmith_project: str = "agentsday"


@dataclass(frozen=True)
class Classification:
    submission_type: SubmissionType
    urls: list[str] = field(default_factory=list)
    primary_url: str | None = None
    x_status_id: str | None = None


@dataclass(frozen=True)
class ResearchDraft:
    title: str
    information: str
    sources: list[str]
    success: bool = True
    error: str | None = None


@dataclass(frozen=True)
class ResearchResult:
    path: Path
    title: str
    submission_type: SubmissionType
    success: bool
    error: str | None = None
