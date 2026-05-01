from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .models import AgentConfig, LoopConfig, ModelConfig, PathsConfig, PromptConfig


def _require_mapping(data: Any, label: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a YAML mapping")
    return data


def _resolve_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return workspace / path


def load_agent_config(config_path: Path, workspace: Path) -> AgentConfig:
    data = _require_mapping(yaml.safe_load(config_path.read_text()) or {}, str(config_path))
    paths = _require_mapping(data.get("paths"), "paths")
    model = _require_mapping(data.get("model"), "model")
    loop = _require_mapping(data.get("loop", {}), "loop")

    return AgentConfig(
        mode=str(data.get("mode", "dev")),
        paths=PathsConfig(
            input_dir=_resolve_path(workspace, str(paths["input_dir"])),
            brain_dir=_resolve_path(workspace, str(paths["brain_dir"])),
            runs_dir=_resolve_path(workspace, str(paths["runs_dir"])),
        ),
        model=ModelConfig(
            provider=str(model.get("provider", "gemini")),
            name=str(model["name"]),
            reasoning_effort=str(model.get("reasoning_effort", "high")),
            thinking_budget=int(model.get("thinking_budget", 2048)),
            temperature=float(model.get("temperature", 0.2)),
        ),
        loop=LoopConfig(max_iterations=int(loop.get("max_iterations", 3))),
    )


def load_prompt_config(prompt_path: Path) -> PromptConfig:
    data = _require_mapping(yaml.safe_load(prompt_path.read_text()) or {}, str(prompt_path))
    return PromptConfig(
        system=str(data.get("system", "")),
        input_contract=str(data.get("input_contract", "")),
        compiler_behavior=list(data.get("compiler_behavior", [])),
        sub_agents=dict(data.get("sub_agents", {})),
    )
