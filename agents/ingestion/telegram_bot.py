from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request

from agents.researcher.service import ResearcherService


ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")

RESET_COMMANDS = {"/new", "/reset", "/clear"}
ASK_COMMAND = "/ask"

app = FastAPI(title="Personal LLM Wiki Telegram Ingestion Bot")

_service: ResearcherService | None = None


def get_service() -> ResearcherService:
    global _service
    if _service is None:
        _service = ResearcherService.from_workspace(ROOT)
    return _service


def send_telegram_message(chat_id: int, text: str) -> None:
    if not BOT_TOKEN:
        return

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, bool]:
    update: dict[str, Any] = await request.json()
    message = update.get("message") or update.get("edited_message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not text:
        if chat_id:
            send_telegram_message(chat_id, "Send me text, a URL, a name, or a question.")
        return {"ok": True}

    stripped = text.strip()
    if stripped.lower() in RESET_COMMANDS:
        if chat_id is not None:
            get_service().clear_qa(chat_id)
            send_telegram_message(chat_id, "Conversation cleared.")
        return {"ok": True}

    if chat_id is None:
        return {"ok": True}

    if _is_ask_command(stripped):
        question = _strip_ask_prefix(stripped)
        if not question:
            send_telegram_message(chat_id, "Usage: /ask <your question about your brain>")
            return {"ok": True}
        send_telegram_message(chat_id, "Received.")
        background_tasks.add_task(process_ask_background, question, chat_id)
        return {"ok": True}

    send_telegram_message(chat_id, "Received.")
    background_tasks.add_task(process_submission_background, text, chat_id)

    return {"ok": True}


def _is_ask_command(stripped: str) -> bool:
    lowered = stripped.lower()
    return lowered == ASK_COMMAND or lowered.startswith(ASK_COMMAND + " ")


def _strip_ask_prefix(stripped: str) -> str:
    return stripped[len(ASK_COMMAND) :].strip()


def process_ask_background(question: str, chat_id: int) -> None:
    try:
        result = get_service().process_ask(question, chat_id)
    except Exception as exc:
        send_telegram_message(chat_id, f"Ask failed: {type(exc).__name__}: {exc}")
        return
    send_telegram_message(chat_id, _format_answer(result.answer, result.sources))


def process_submission_background(text: str, chat_id: int | None) -> None:
    if chat_id is None:
        try:
            get_service().process_submission(text)
        except Exception:
            return
        return

    service = get_service()
    if service.conversations.has(chat_id):
        try:
            cont = service.continue_qa(text, chat_id)
        except Exception as exc:
            send_telegram_message(chat_id, f"Research failed: {type(exc).__name__}: {exc}")
            return

        if cont.kind == "saved" and cont.save_result is not None:
            send_telegram_message(
                chat_id,
                f"Saved as a new note instead.\n{_format_save(cont.save_result)}",
            )
            return
        send_telegram_message(chat_id, _format_answer(cont.answer, cont.sources))
        return

    try:
        result = service.process_submission(text)
    except Exception as exc:
        send_telegram_message(chat_id, f"Research failed: {type(exc).__name__}: {exc}")
        return
    send_telegram_message(chat_id, _format_save(result))


def _format_answer(answer: str, sources: list[str]) -> str:
    if not sources:
        return answer
    sources_block = "\n".join(f"- {src}" for src in sources)
    return f"{answer}\n\nSources:\n{sources_block}"


def _format_save(result) -> str:
    relative_path = _safe_relative(result.path)
    if result.success:
        return f'New note: "{result.title}" ({relative_path})'
    return f'Problem saving note: {result.error or "unknown"} ({relative_path})'


def _safe_relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("agents.ingestion.telegram_bot:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
