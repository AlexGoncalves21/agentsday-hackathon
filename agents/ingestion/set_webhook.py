from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    load_dotenv(ROOT / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    base_url = os.getenv("TELEGRAM_WEBHOOK_BASE_URL", "").rstrip("/")
    path = os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")

    if not token or token == "replace_me":
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env")
    if not base_url or "replace-me" in base_url:
        raise SystemExit("Missing TELEGRAM_WEBHOOK_BASE_URL in .env")

    webhook_url = f"{base_url}{path}"
    response = requests.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data={"url": webhook_url},
        timeout=15,
    )
    response.raise_for_status()

    print(f"Webhook set to {webhook_url}")
    print(response.text)


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Failed to set Telegram webhook: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
