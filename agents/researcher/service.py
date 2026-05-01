from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from .brain import BrainReader
from .classifier import classify_submission, extract_urls
from .clients import (
    ApifyTweetClient,
    GeminiResearchClient,
    _payload_links,
    run_with_langsmith,
    tweet_to_draft,
)
from .config import load_research_config
from .conversation import ConversationManager, ConversationSession
from .markdown import failure_draft, note_draft, write_input_markdown
from .models import Classification, ResearchConfig, ResearchDraft, ResearchResult
from .trace import ResearchTraceRecorder


AskKind = Literal["answered", "no_match", "error"]
ContinueKind = Literal["answered", "no_match", "saved", "error"]


@dataclass(frozen=True)
class AskResult:
    kind: AskKind
    answer: str
    sources: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class ContinueResult:
    kind: ContinueKind
    answer: str = ""
    sources: list[str] = field(default_factory=list)
    save_result: ResearchResult | None = None
    error: str | None = None


class ResearcherService:
    def __init__(self, config: ResearchConfig, workspace: Path) -> None:
        self.config = config
        self.workspace = workspace
        self.trace = ResearchTraceRecorder(config.runs_dir)
        self.apify = ApifyTweetClient(config.apify_api_token, config.timeout_seconds)
        self.gemini = GeminiResearchClient(config.gemini_api_key, config.gemini_model, config.timeout_seconds)
        self.brain = BrainReader(config.brain_dir)
        self.conversations = ConversationManager()

    @classmethod
    def from_workspace(cls, workspace: Path) -> "ResearcherService":
        return cls(load_research_config(workspace), workspace)

    def process_submission(self, text: str) -> ResearchResult:
        draft, path, classification = self._process_and_save(text)
        return ResearchResult(
            path=path,
            title=draft.title,
            submission_type=classification.submission_type,
            success=draft.success,
            error=draft.error,
        )

    def process_ask(self, question: str, chat_id: int) -> AskResult:
        session = ConversationSession(chat_id=chat_id)
        self.conversations.set(session)
        result = self._answer_from_brain(question, session)
        session.append("user", question)
        session.append("assistant", result.answer)
        return result

    def continue_qa(self, message: str, chat_id: int) -> ContinueResult:
        session = self.conversations.get(chat_id)
        if session is None:
            saved = self.process_submission(message)
            return ContinueResult(kind="saved", save_result=saved)

        if extract_urls(message):
            self.conversations.clear(chat_id)
            saved = self.process_submission(message)
            self.trace.event(
                "qa_exit_url",
                "Q&A exited via URL short-circuit",
                chat_id=chat_id,
                output_path=self._repo_rel(saved.path),
            )
            return ContinueResult(kind="saved", save_result=saved)

        decision = self.gemini.route_qa_message(
            recent_history=session.recent_history(),
            new_text=message,
        )
        self.trace.event(
            "qa_router",
            "Routed Q&A message",
            chat_id=chat_id,
            decision=decision,
        )
        if decision == "save":
            self.conversations.clear(chat_id)
            saved = self.process_submission(message)
            return ContinueResult(kind="saved", save_result=saved)

        ask = self._answer_from_brain(message, session)
        session.append("user", message)
        session.append("assistant", ask.answer)
        return ContinueResult(
            kind=ask.kind,
            answer=ask.answer,
            sources=ask.sources,
            error=ask.error,
        )

    def clear_qa(self, chat_id: int) -> None:
        self.conversations.clear(chat_id)

    def _answer_from_brain(self, question: str, session: ConversationSession) -> AskResult:
        try:
            index_md = self.brain.read_index()
        except FileNotFoundError as exc:
            return AskResult(
                kind="error",
                answer="The brain index is not available yet. Run the Organizer to compile your notes.",
                sources=[],
                error=str(exc),
            )

        history_str = session.recent_history()
        try:
            picked = self.gemini.pick_brain_notes(
                question=question,
                index_md=index_md,
                recent_history=history_str,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.trace.event("brain_pick_failed", "pick_brain_notes raised", error=error)
            return AskResult(kind="error", answer=f"Could not look up your brain: {error}", sources=[], error=error)

        available = self.brain.available_paths()
        valid_paths: list[str] = []
        for raw in picked:
            normalized = self.brain.normalize(raw)
            if normalized in available:
                valid_paths.append(normalized)

        if not valid_paths:
            self.trace.event(
                "brain_no_match",
                "No brain notes selected for question",
                chat_id=session.chat_id,
                picked=list(picked),
            )
            return AskResult(
                kind="no_match",
                answer="Nothing in your brain matches that yet. Send the topic as a plain message to save a new note for it.",
                sources=[],
            )

        notes: list[tuple[str, str]] = []
        for rel_path in valid_paths:
            try:
                content = self.brain.read_note(rel_path)
            except (FileNotFoundError, ValueError) as exc:
                self.trace.event(
                    "brain_read_failed",
                    "Failed to read picked brain note",
                    rel_path=rel_path,
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue
            notes.append((rel_path, content))

        if not notes:
            return AskResult(
                kind="no_match",
                answer="Nothing in your brain matches that yet. Send the topic as a plain message to save a new note for it.",
                sources=[],
            )

        try:
            answer = self.gemini.answer_from_brain(
                question=question,
                notes=notes,
                recent_history=history_str,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.trace.event("brain_answer_failed", "answer_from_brain raised", error=error)
            return AskResult(kind="error", answer=f"Could not generate an answer: {error}", sources=[], error=error)

        sources = [f"brain/{rel}" for rel, _ in notes]
        self.trace.event(
            "brain_answered",
            "Answered from brain",
            chat_id=session.chat_id,
            sources=sources,
        )
        return AskResult(kind="answered", answer=answer, sources=sources)

    def _process_and_save(self, text: str) -> tuple[ResearchDraft, Path, Classification]:
        timestamp = datetime.now()
        classification = classify_submission(text)
        started = datetime.now()

        def _run() -> ResearchDraft:
            return self._draft_for_submission(text, timestamp)

        def _run_and_save() -> tuple[ResearchDraft, Path]:
            self.trace.event(
                "start",
                "Starting researcher submission",
                submission_type=classification.submission_type,
                url_count=len(classification.urls),
            )
            try:
                draft = _run()
            except Exception as exc:
                draft = failure_draft(
                    title=_fallback_title(text),
                    submitted=text,
                    reason=f"{type(exc).__name__}: {exc}",
                    sources=classification.urls,
                )

            path = write_input_markdown(self.config.input_dir, draft, timestamp)
            duration = (datetime.now() - started).total_seconds()
            self.trace.event(
                "finish",
                "Finished researcher submission",
                submission_type=classification.submission_type,
                success=draft.success,
                duration_seconds=duration,
                output_path=self._repo_rel(path),
                error=draft.error,
            )
            return draft, path

        draft, path = run_with_langsmith(
            self.config,
            name=f"researcher:{classification.submission_type}",
            metadata={
                "submission_type": classification.submission_type,
                "route": classification.submission_type,
                "url_count": len(classification.urls),
            },
            func=_run_and_save,
        )
        return draft, path, classification

    def _draft_for_submission(self, text: str, timestamp: datetime) -> ResearchDraft:
        classification = classify_submission(text)
        if classification.submission_type == "note":
            return note_draft(text, timestamp)

        if classification.submission_type == "x_url":
            post = self.apify.fetch_post(classification.primary_url or classification.urls[0], classification.x_status_id)
            linked_urls = _payload_links(post.source_payload)
            try:
                return self.gemini.enrich_tweet(post, linked_urls)
            except Exception as exc:
                self.trace.event(
                    "tweet_enrich_failed",
                    "Falling back to plain tweet capture",
                    error=f"{type(exc).__name__}: {exc}",
                )
                return tweet_to_draft(post)

        if classification.submission_type in {"web_url", "question", "topic_or_concept"}:
            return self.gemini.research(text, classification.submission_type, classification.urls)

        return failure_draft(
            title=_fallback_title(text),
            submitted=text,
            reason=f"Unsupported submission type: {classification.submission_type}",
            sources=classification.urls,
        )

    def _repo_rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.workspace.resolve()).as_posix()
        except ValueError:
            return str(path)


def _fallback_title(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    return cleaned[:80].rstrip(" .,:;") or "Submission"
