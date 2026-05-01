from __future__ import annotations

import sys
from pathlib import Path

from .models import AgentConfig, PromptConfig


def build_model_string(config: AgentConfig) -> str:
    provider = config.model.provider.lower()
    if provider in {"gemini", "google", "google_genai"}:
        return f"google_genai:{config.model.name}"
    return f"{config.model.provider}:{config.model.name}"


def run_deep_agent(config: AgentConfig, prompts: PromptConfig, workspace: Path) -> str:
    if sys.version_info < (3, 11):
        version = ".".join(map(str, sys.version_info[:3]))
        raise RuntimeError(
            f"The LLM-backed Organizer requires Python 3.11+ because `deepagents` requires it. "
            f"You are running Python {version}. Use a Python 3.11+ virtualenv/conda env."
        )
    try:
        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend
    except ImportError as exc:
        raise RuntimeError(
            "Deep Agents dependencies are not installed. Run `python3 -m pip install -e .` "
            "or install `deepagents langchain-google-genai`."
        ) from exc

    behavior = "\n".join(f"- {item}" for item in prompts.compiler_behavior)
    sub_agents = "\n".join(f"{name}: {prompt}" for name, prompt in prompts.sub_agents.items())
    system_prompt = "\n\n".join(
        [
            prompts.system,
            prompts.input_contract,
            "Compiler behavior:\n" + behavior,
            "Sub-agent roles:\n" + sub_agents,
        ]
    )
    agent = create_deep_agent(
        model=build_model_string(config),
        backend=FilesystemBackend(root_dir=str(workspace.resolve()), virtual_mode=True),
        tools=[],
        system_prompt=system_prompt,
    )
    user_prompt = f"""
Compile the personal second brain in this workspace.

Read every Markdown file from input/.
In dev mode, rebuild brain/ from scratch.
Write a fresh report to runs/latest_report.md.
Delete each input Markdown file after it has been successfully represented in brain/ and summarized under brain/sources/.
Do not use previous run reports as context.
"""
    result = agent.invoke({"messages": [{"role": "user", "content": user_prompt.strip()}]})
    return str(result)
