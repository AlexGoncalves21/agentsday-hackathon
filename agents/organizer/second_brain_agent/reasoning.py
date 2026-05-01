from __future__ import annotations

import os
from typing import Dict, List

from .models import AgentConfig, BrainPage, InputDocument, PromptConfig

try:
    from langsmith import traceable
except ImportError:  # pragma: no cover - exercised only in deterministic/dev environments.

    def traceable(*_args, **_kwargs):  # type: ignore[no-redef]
        def decorator(func):
            return func

        return decorator


class OrganizerReasoner:
    def __init__(self, config: AgentConfig, prompts: PromptConfig) -> None:
        self.config = config
        self.prompts = prompts
        self.model = build_reasoning_model(config)

    @traceable(name="organizer_critic_reasoning", run_type="chain")
    def critique_page_plan(
        self,
        iteration: int,
        docs: List[InputDocument],
        pages: Dict[str, BrainPage],
        deterministic_issues: List[str],
    ) -> str:
        messages = [
            (
                "system",
                "\n\n".join(
                    [
                        self.prompts.system,
                        "You are the Organizer critic. Use deliberate private reasoning, then return only concise actionable critique. "
                        "Do not reveal chain-of-thought. Focus on missing inputs, bad merges, weak links, duplicate pages, and source fidelity.",
                    ]
                ),
            ),
            (
                "human",
                self._critique_prompt(iteration, docs, pages, deterministic_issues),
            ),
        ]
        response = self.model.invoke(messages)
        return _message_text(getattr(response, "content", response))

    def _critique_prompt(
        self,
        iteration: int,
        docs: List[InputDocument],
        pages: Dict[str, BrainPage],
        deterministic_issues: List[str],
    ) -> str:
        input_summary = "\n".join(
            f"- {doc.path.name}: {doc.title}\n  {doc.information[:700].strip()}" for doc in docs
        )
        page_summary = "\n".join(
            f"- {page.slug}: title={page.title!r}, category={page.category}, related={page.related_slugs}"
            for page in pages.values()
        )
        issue_summary = "\n".join(f"- {issue}" for issue in deterministic_issues) or "- none"
        return f"""Iteration: {iteration}

Inputs:
{input_summary}

Planned pages:
{page_summary}

Deterministic critique:
{issue_summary}

Return:
- PASS if the plan is coherent.
- Otherwise, bullets with concrete fixes the compiler should make.
"""


def build_reasoning_model(config: AgentConfig):
    provider = config.model.provider.lower()
    if provider in {"gemini", "google", "google_genai"}:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError(
                "The Organizer reasoning path requires `langchain-google-genai`. "
                "Install the project dependencies in a Python 3.11+ environment with `python3 -m pip install -e .`."
            ) from exc

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        common_kwargs = {
            "model": config.model.name,
            "temperature": config.model.temperature,
        }
        if api_key:
            common_kwargs["google_api_key"] = api_key

        attempts = []
        if config.model.name.startswith("gemini-3"):
            attempts.append({**common_kwargs, "thinking_level": config.model.reasoning_effort})
        attempts.append({**common_kwargs, "thinking_budget": config.model.thinking_budget})
        attempts.append(common_kwargs)

        last_error: Exception | None = None
        for kwargs in attempts:
            try:
                return ChatGoogleGenerativeAI(**kwargs)
            except (TypeError, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"Unable to configure Gemini reasoning model: {last_error}") from last_error

    return _init_chat_model(config)


def _init_chat_model(config: AgentConfig):
    try:
        from langchain.chat_models import init_chat_model
    except ImportError as exc:
        raise RuntimeError(
            "The Organizer reasoning path requires LangChain model dependencies. "
            "Install the project dependencies in a Python 3.11+ environment with `python3 -m pip install -e .`."
        ) from exc
    return init_chat_model(f"{config.model.provider}:{config.model.name}", temperature=config.model.temperature)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(text_parts).strip()
    return str(content).strip()
