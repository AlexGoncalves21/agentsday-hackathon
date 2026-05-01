from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .classifier import classify_submission
from .clients import (
    ApifyTweetClient,
    GeminiResearchClient,
    _payload_links,
    run_with_langsmith,
    tweet_to_draft,
)
from .config import load_research_config
from .conversation import ConversationManager, ConversationResult, ConversationSession
from .markdown import failure_draft, note_draft, render_markdown, write_input_markdown
from .models import Classification, ResearchConfig, ResearchDraft, ResearchResult
from .trace import ResearchTraceRecorder


class ResearcherService:
    def __init__(self, config: ResearchConfig, workspace: Path) -> None:
        self.config = config
        self.workspace = workspace
        self.trace = ResearchTraceRecorder(config.runs_dir)
        self.apify = ApifyTweetClient(config.apify_api_token, config.timeout_seconds)
        self.gemini = GeminiResearchClient(config.gemini_api_key, config.gemini_model, config.timeout_seconds)
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

    def process_conversational(self, text: str, chat_id: int) -> ConversationResult:
        session = self.conversations.get(chat_id)
        if session is None:
            return self._start_topic(text, chat_id)

        decision = self.gemini.route_followup(
            session_title=session.title,
            recent_history=session.recent_history(),
            new_text=text,
        )
        self.trace.event(
            "router",
            "Routed conversational message",
            chat_id=chat_id,
            decision=decision,
            session_title=session.title,
        )
        if decision == "new_topic":
            self.conversations.clear(chat_id)
            return self._start_topic(text, chat_id)
        return self._refine_topic(session, text)

    def reset_conversation(self, chat_id: int) -> None:
        self.conversations.clear(chat_id)

    def _start_topic(self, text: str, chat_id: int) -> ConversationResult:
        draft, path, classification = self._process_and_save(text)
        summary = _initial_summary(draft)

        if draft.success:
            session = ConversationSession(
                chat_id=chat_id,
                title=draft.title,
                path=path,
                draft=draft,
                submission_type=classification.submission_type,
            )
            session.append("user", text)
            session.append("assistant", summary)
            self.conversations.set(session)

        return ConversationResult(
            path=path,
            title=draft.title,
            action="new_topic" if draft.success else "failed",
            summary=summary,
            success=draft.success,
            error=draft.error,
        )

    def _refine_topic(self, session: ConversationSession, text: str) -> ConversationResult:
        current_markdown = render_markdown(session.draft)
        try:
            new_draft, summary = self.gemini.refine(
                current_markdown=current_markdown,
                recent_history=session.recent_history(),
                feedback=text,
                existing_sources=list(session.draft.sources),
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.trace.event(
                "refine_failed",
                "Refinement failed",
                chat_id=session.chat_id,
                error=error,
            )
            return ConversationResult(
                path=session.path,
                title=session.title,
                action="failed",
                summary=f"Could not apply that feedback: {error}",
                success=False,
                error=error,
            )

        session.path.write_text(render_markdown(new_draft), encoding="utf-8")
        session.draft = new_draft
        session.title = new_draft.title
        session.append("user", text)
        session.append("assistant", summary)
        self.conversations.set(session)

        self.trace.event(
            "refined",
            "Refined existing note",
            chat_id=session.chat_id,
            output_path=self._repo_rel(session.path),
            title=new_draft.title,
        )

        return ConversationResult(
            path=session.path,
            title=new_draft.title,
            action="refined",
            summary=summary,
            success=True,
        )

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


def _initial_summary(draft: ResearchDraft) -> str:
    if not draft.success:
        return f"Saved a failed extraction. Reason: {draft.error or 'unknown'}"
    info = " ".join(draft.information.split())
    snippet = info[:280].rstrip()
    if len(info) > 280:
        snippet += "..."
    return (
        f'Saved "{draft.title}".\n\n{snippet}\n\n'
        "Reply with feedback to refine this note, or send a new topic to start a fresh one."
    )
