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
            get_service().reset_conversation(chat_id)
            send_telegram_message(chat_id, "Conversation reset. Send a new topic to start.")
        return {"ok": True}

    if chat_id is None:
        return {"ok": True}

    send_telegram_message(chat_id, "Received.")

    background_tasks.add_task(process_submission_background, text, chat_id)

    return {"ok": True}


def process_submission_background(text: str, chat_id: int | None) -> None:
    if chat_id is None:
        try:
            get_service().process_submission(text)
        except Exception:
            return
        return

    try:
        result = get_service().process_conversational(text, chat_id)
    except Exception as exc:
        send_telegram_message(chat_id, f"Research failed: {type(exc).__name__}: {exc}")
        return

    relative_path = _safe_relative(result.path)
    header = {
        "new_topic": f'New note: "{result.title}" ({relative_path})',
        "refined": f'Updated "{result.title}" ({relative_path})',
        "failed": f"Problem with that message ({relative_path})",
    }.get(result.action, relative_path)

    send_telegram_message(chat_id, f"{header}\n\n{result.summary}")


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
