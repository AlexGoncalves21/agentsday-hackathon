from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class PathsConfig:
    input_dir: Path
    brain_dir: Path
    runs_dir: Path


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    name: str


@dataclass(frozen=True)
class LoopConfig:
    max_iterations: int = 3


@dataclass(frozen=True)
class AgentConfig:
    mode: str
    paths: PathsConfig
    model: ModelConfig
    loop: LoopConfig


@dataclass(frozen=True)
class PromptConfig:
    system: str
    input_contract: str
    compiler_behavior: List[str]
    sub_agents: Dict[str, str]


@dataclass(frozen=True)
class InputDocument:
    path: Path
    title: str
    information: str
    sources: List[str]
    slug: str


@dataclass(frozen=True)
class BrainPage:
    title: str
    category: str
    slug: str
    path: Path
    source_doc: InputDocument
    related_slugs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    details: str

