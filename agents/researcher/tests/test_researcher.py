from __future__ import annotations

import shutil
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from agents.organizer.second_brain_agent.markdown import parse_input_document
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
            config = ResearchConfig(input_dir=workspace / "input", runs_dir=workspace / "runs")
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
            config = ResearchConfig(input_dir=workspace / "input", runs_dir=workspace / "runs")
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
            config = ResearchConfig(input_dir=workspace / "input", runs_dir=workspace / "runs")
            service = ResearcherService(config, workspace)
            service.apify = FakeApify(error=RuntimeError("no exact post"))  # type: ignore[assignment]

            result = service.process_submission("https://x.com/example/status/123")

            document = parse_input_document(result.path)
            self.assertFalse(result.success)
            self.assertTrue(document.title.startswith("Failed Extraction:"))
            self.assertEqual(document.sources, ["https://x.com/example/status/123"])
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
