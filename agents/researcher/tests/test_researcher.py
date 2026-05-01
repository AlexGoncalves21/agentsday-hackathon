from __future__ import annotations

import shutil
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from agents.organizer.second_brain_agent.markdown import parse_input_document
from agents.researcher.brain import BrainReader
from agents.researcher.classifier import classify_submission
from agents.researcher.clients import TweetPost, tweet_to_draft
from agents.researcher.markdown import failure_draft, note_draft, render_markdown, write_input_markdown
from agents.researcher.models import ResearchConfig, ResearchDraft
from agents.researcher.service import ResearcherService


def test_workspace() -> Path:
    path = Path.cwd() / ".test-tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_workspace(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


class ResearcherClassifierTests(unittest.TestCase):
    def test_classifies_exact_x_status_url(self) -> None:
        result = classify_submission("https://x.com/example/status/1234567890")

        self.assertEqual(result.submission_type, "x_url")
        self.assertEqual(result.primary_url, "https://x.com/example/status/1234567890")
        self.assertEqual(result.x_status_id, "1234567890")

    def test_classifies_question_topic_and_note(self) -> None:
        self.assertEqual(classify_submission("What is LangGraph?").submission_type, "question")
        self.assertEqual(classify_submission("Decision theory").submission_type, "topic_or_concept")
        self.assertEqual(classify_submission("buy milk and call ana tomorrow").submission_type, "note")


class ResearcherMarkdownTests(unittest.TestCase):
    def test_note_markdown_validates_against_organizer_contract(self) -> None:
        workspace = test_workspace()
        try:
            draft = note_draft("remember to review the agent demo", datetime(2026, 5, 1, 12, 0, 0))
            path = write_input_markdown(workspace, draft, datetime(2026, 5, 1, 12, 0, 0))

            document = parse_input_document(path)
        finally:
            cleanup_workspace(workspace)

        self.assertEqual(document.title, "remember to review the agent demo")
        self.assertEqual(document.sources, ["telegram://submission/20260501120000"])

    def test_failure_markdown_keeps_valid_contract(self) -> None:
        draft = failure_draft("Example", "https://example.com", "timeout", ["https://example.com"])
        rendered = render_markdown(draft)

        self.assertIn("# Failed Extraction: Example", rendered)
        self.assertIn("## Information", rendered)
        self.assertIn("## Sources", rendered)
        self.assertIn("- https://example.com", rendered)


class FakeGemini:
    def research(self, text: str, route: str, source_urls: list[str]) -> ResearchDraft:
        return ResearchDraft(
            title="Gemini Result",
            information=f"Route: {route}. Submitted: {text}.",
            sources=source_urls or ["https://example.com/source"],
        )


class FakeApify:
    def __init__(self, post: TweetPost | None = None, error: Exception | None = None) -> None:
        self.post = post
        self.error = error

    def fetch_post(self, url: str, expected_status_id: str | None) -> TweetPost:
        if self.error:
            raise self.error
        assert self.post is not None
        return self.post


class ResearcherServiceTests(unittest.TestCase):
    def test_processes_topic_with_gemini_client(self) -> None:
        workspace = test_workspace()
        try:
            config = ResearchConfig(input_dir=workspace / "input", runs_dir=workspace / "runs", brain_dir=workspace / "brain")
            service = ResearcherService(config, workspace)
            service.gemini = FakeGemini()  # type: ignore[assignment]

            result = service.process_submission("LangGraph")

            document = parse_input_document(result.path)
            self.assertTrue(result.success)
            self.assertEqual(document.title, "Gemini Result")
            self.assertEqual(document.sources, ["https://example.com/source"])
        finally:
            cleanup_workspace(workspace)

    def test_processes_x_url_with_exact_post_client(self) -> None:
        workspace = test_workspace()
        try:
            config = ResearchConfig(input_dir=workspace / "input", runs_dir=workspace / "runs", brain_dir=workspace / "brain")
            service = ResearcherService(config, workspace)
            service.apify = FakeApify(
                TweetPost(
                    text="Original linked post",
                    author="example",
                    created_at="2026-05-01T12:00:00Z",
                    url="https://x.com/example/status/123",
                    source_payload={"url": "https://x.com/example/status/123"},
                )
            )  # type: ignore[assignment]

            result = service.process_submission("https://x.com/example/status/123")

            document = parse_input_document(result.path)
            self.assertTrue(result.success)
            self.assertIn("Original linked post", document.information)
            self.assertEqual(document.sources, ["https://x.com/example/status/123"])
        finally:
            cleanup_workspace(workspace)

    def test_apify_failure_still_saves_valid_failed_extraction(self) -> None:
        workspace = test_workspace()
        try:
            config = ResearchConfig(input_dir=workspace / "input", runs_dir=workspace / "runs", brain_dir=workspace / "brain")
            service = ResearcherService(config, workspace)
            service.apify = FakeApify(error=RuntimeError("no exact post"))  # type: ignore[assignment]

            result = service.process_submission("https://x.com/example/status/123")

            document = parse_input_document(result.path)
            self.assertFalse(result.success)
            self.assertTrue(document.title.startswith("Failed Extraction:"))
            self.assertEqual(document.sources, ["https://x.com/example/status/123"])
        finally:
            cleanup_workspace(workspace)


class BrainReaderTests(unittest.TestCase):
    def _make_brain(self, workspace: Path) -> Path:
        brain_dir = workspace / "brain"
        (brain_dir / "concepts").mkdir(parents=True)
        (brain_dir / "index.md").write_text("# Index\n- concepts/x.md\n", encoding="utf-8")
        (brain_dir / "concepts" / "x.md").write_text("# X\n\nBody.\n", encoding="utf-8")
        return brain_dir

    def test_read_index_and_note(self) -> None:
        workspace = test_workspace()
        try:
            brain_dir = self._make_brain(workspace)
            reader = BrainReader(brain_dir)

            self.assertIn("# Index", reader.read_index())
            self.assertIn("Body.", reader.read_note("concepts/x.md"))
            self.assertIn("Body.", reader.read_note("brain/concepts/x.md"))
            self.assertEqual(reader.available_paths(), {"index.md", "concepts/x.md"})
        finally:
            cleanup_workspace(workspace)

    def test_read_note_rejects_path_traversal(self) -> None:
        workspace = test_workspace()
        try:
            brain_dir = self._make_brain(workspace)
            outside = workspace / "secret.md"
            outside.write_text("nope", encoding="utf-8")
            reader = BrainReader(brain_dir)

            with self.assertRaises(ValueError):
                reader.read_note("../secret.md")
        finally:
            cleanup_workspace(workspace)

    def test_read_index_missing_raises(self) -> None:
        workspace = test_workspace()
        try:
            brain_dir = workspace / "brain"
            brain_dir.mkdir()
            reader = BrainReader(brain_dir)

            with self.assertRaises(FileNotFoundError):
                reader.read_index()
        finally:
            cleanup_workspace(workspace)


class FakeBrainGemini:
    def __init__(self, picks: list[str], answer: str) -> None:
        self.picks = picks
        self.answer = answer
        self.last_question: str | None = None
        self.last_notes: list[tuple[str, str]] | None = None

    def pick_brain_notes(self, question: str, index_md: str, recent_history: str, max_notes: int = 3) -> list[str]:
        self.last_question = question
        return list(self.picks)

    def answer_from_brain(self, question: str, notes: list[tuple[str, str]], recent_history: str) -> str:
        self.last_notes = list(notes)
        return self.answer

    def route_qa_message(self, recent_history: str, new_text: str) -> str:
        return "continue"


class ProcessAskTests(unittest.TestCase):
    def _make_brain(self, workspace: Path) -> None:
        brain_dir = workspace / "brain"
        (brain_dir / "concepts").mkdir(parents=True)
        (brain_dir / "index.md").write_text(
            "# Brain Index\n\n## Concepts\n\n- [Decision Theory](concepts/decision-theory.md)\n",
            encoding="utf-8",
        )
        (brain_dir / "concepts" / "decision-theory.md").write_text(
            "# Decision Theory\n\nA framework for choosing under uncertainty.\n",
            encoding="utf-8",
        )

    def _service(self, workspace: Path) -> ResearcherService:
        config = ResearchConfig(
            input_dir=workspace / "input",
            runs_dir=workspace / "runs",
            brain_dir=workspace / "brain",
        )
        return ResearcherService(config, workspace)

    def test_process_ask_answers_with_sources(self) -> None:
        workspace = test_workspace()
        try:
            self._make_brain(workspace)
            service = self._service(workspace)
            fake = FakeBrainGemini(
                picks=["concepts/decision-theory.md"],
                answer="It's a framework for choosing under uncertainty.",
            )
            service.gemini = fake  # type: ignore[assignment]

            result = service.process_ask("what is decision theory?", chat_id=7)

            self.assertEqual(result.kind, "answered")
            self.assertEqual(result.sources, ["brain/concepts/decision-theory.md"])
            self.assertIn("framework", result.answer)
            self.assertIsNotNone(fake.last_notes)
            assert fake.last_notes is not None
            self.assertEqual(fake.last_notes[0][0], "concepts/decision-theory.md")
            self.assertTrue(service.conversations.has(7))
        finally:
            cleanup_workspace(workspace)

    def test_process_ask_no_match_keeps_session(self) -> None:
        workspace = test_workspace()
        try:
            self._make_brain(workspace)
            service = self._service(workspace)
            service.gemini = FakeBrainGemini(picks=[], answer="(unused)")  # type: ignore[assignment]

            result = service.process_ask("what is k8s?", chat_id=9)

            self.assertEqual(result.kind, "no_match")
            self.assertEqual(result.sources, [])
            self.assertTrue(service.conversations.has(9))
        finally:
            cleanup_workspace(workspace)

    def test_process_ask_drops_invalid_paths(self) -> None:
        workspace = test_workspace()
        try:
            self._make_brain(workspace)
            service = self._service(workspace)
            service.gemini = FakeBrainGemini(
                picks=["concepts/does-not-exist.md", "../secret.md"],
                answer="(unused)",
            )  # type: ignore[assignment]

            result = service.process_ask("anything", chat_id=11)

            self.assertEqual(result.kind, "no_match")
        finally:
            cleanup_workspace(workspace)

    def test_continue_qa_routes_url_to_save(self) -> None:
        workspace = test_workspace()
        try:
            self._make_brain(workspace)
            service = self._service(workspace)
            fake = FakeBrainGemini(
                picks=["concepts/decision-theory.md"],
                answer="answer",
            )

            class _GeminiWithResearch(FakeBrainGemini):
                def research(self, text: str, route: str, source_urls: list[str]) -> ResearchDraft:
                    return ResearchDraft(
                        title="Web Note",
                        information=f"Saved {text}",
                        sources=source_urls or [text],
                    )

            service.gemini = _GeminiWithResearch(picks=fake.picks, answer=fake.answer)  # type: ignore[assignment]

            service.process_ask("what is decision theory?", chat_id=21)
            cont = service.continue_qa("https://example.com/article", chat_id=21)

            self.assertEqual(cont.kind, "saved")
            self.assertIsNotNone(cont.save_result)
            self.assertFalse(service.conversations.has(21))
        finally:
            cleanup_workspace(workspace)


class TelegramWebhookTests(unittest.TestCase):
    def test_webhook_acknowledges_and_schedules_background_research(self) -> None:
        from fastapi.testclient import TestClient

        from agents.ingestion import telegram_bot

        calls: list[tuple[str, int | None]] = []
        messages: list[str] = []

        def fake_background(text: str, chat_id: int | None) -> None:
            calls.append((text, chat_id))

        def fake_send(chat_id: int, text: str) -> None:
            messages.append(text)

        with patch.object(telegram_bot, "process_submission_background", fake_background), patch.object(
            telegram_bot, "send_telegram_message", fake_send
        ):
            response = TestClient(telegram_bot.app).post(
                telegram_bot.WEBHOOK_PATH,
                json={"message": {"text": "LangGraph", "chat": {"id": 42}}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(calls, [("LangGraph", 42)])
        self.assertEqual(messages, ["Received."])


if __name__ == "__main__":
    unittest.main()
