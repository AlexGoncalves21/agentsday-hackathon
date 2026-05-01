from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import requests

from .models import ResearchConfig, ResearchDraft


T = TypeVar("T")


@dataclass(frozen=True)
class TweetPost:
    text: str
    author: str
    created_at: str
    url: str
    source_payload: dict[str, Any]


def run_with_langsmith(
    config: ResearchConfig,
    name: str,
    metadata: dict[str, Any],
    func: Callable[[], T],
) -> T:
    if not config.langsmith_tracing:
        return func()
    try:
        from langsmith import traceable
    except ImportError:
        return func()

    wrapped = traceable(name=name, run_type="chain", metadata=metadata)(func)
    return wrapped()


class ApifyTweetClient:
    actor_id = "apidojo~tweet-scraper"

    def __init__(self, token: str, timeout_seconds: int) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds

    def fetch_post(self, url: str, expected_status_id: str | None) -> TweetPost:
        if not self.token:
            raise RuntimeError("APIFY_API_TOKEN is not set")

        endpoint = f"https://api.apify.com/v2/acts/{self.actor_id}/run-sync-get-dataset-items"
        payload = {
            "startUrls": [url],
            "maxItems": 1,
        }
        response = requests.post(
            endpoint,
            params={"token": self.token},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        items = response.json()
        if not isinstance(items, list) or not items:
            raise RuntimeError("Apify returned no tweet items")

        for item in items:
            if not isinstance(item, dict):
                continue
            item_url = _first_string(item, ["url", "twitterUrl", "tweetUrl"])
            item_id = _first_string(item, ["id", "tweetId", "rest_id", "conversationId"])
            if expected_status_id and not _tweet_matches(item_url, item_id, expected_status_id):
                continue
            text = _first_string(item, ["text", "fullText", "content", "tweetText"])
            if not text:
                raise RuntimeError("Apify tweet item did not include post text")
            author = _author_name(item)
            created_at = _first_string(item, ["createdAt", "created_at", "date", "timestamp"])
            return TweetPost(
                text=text,
                author=author or "Unknown author",
                created_at=created_at or "Unknown time",
                url=item_url or url,
                source_payload=item,
            )

        raise RuntimeError("Apify did not return the exact linked X/Twitter post")


class GeminiResearchClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def research(self, submission: str, route: str, source_urls: list[str]) -> ResearchDraft:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc

        client = genai.Client(api_key=self.api_key)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(
            tools=[grounding_tool],
            temperature=0.2,
        )
        response = client.models.generate_content(
            model=self.model,
            contents=_gemini_prompt(submission, route, source_urls),
            config=config,
        )
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty research response")

        title, information, inline_sources = _parse_model_markdown(text)
        sources = list(dict.fromkeys(source_urls + inline_sources + _grounding_sources(response)))
        if not sources:
            raise RuntimeError("Gemini returned no source URLs")
        return ResearchDraft(title=title, information=information, sources=sources)

    def route_followup(self, session_title: str, recent_history: str, new_text: str) -> str:
        if not self.api_key:
            return "continue"
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return "continue"

        client = genai.Client(api_key=self.api_key)
        prompt = f"""You are a router for a personal research note assistant.

The user is currently building a note titled: "{session_title}"

Recent conversation:
{recent_history}

New user message:
{new_text}

Decide whether the new message is FEEDBACK or an ADDITION that refines the current note, or a NEW unrelated topic that should start its own note.

Heuristics:
- Pure URLs, new question, or new concept name unrelated to the current title -> NEW_TOPIC.
- "also add", "fix", "no, I meant", "expand on", "wrong", clarifications, follow-up questions about the same subject -> CONTINUE.

Reply with exactly one word: CONTINUE or NEW_TOPIC.
"""
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0),
            )
        except Exception:
            return "new_topic"
        text = (getattr(response, "text", "") or "").strip().upper()
        if "NEW_TOPIC" in text:
            return "new_topic"
        if "CONTINUE" in text:
            return "continue"
        return "new_topic"

    def enrich_tweet(self, post: "TweetPost", linked_urls: list[str]) -> ResearchDraft:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc

        client = genai.Client(api_key=self.api_key)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool], temperature=0.2)
        linked_lines = "\n".join(f"- {url}" for url in linked_urls) or "- (none)"
        prompt = f"""You are the Researcher for a personal second brain.

A user submitted this X/Twitter post. Use Google Search grounding to add context the post alone does not provide.

Post URL: {post.url}
Author handle / name: {post.author}
Created at: {post.created_at}
Linked or media URLs in the post:
{linked_lines}

Post text:
\"\"\"
{post.text.strip()}
\"\"\"

Write a dense Markdown note in EXACTLY this structure:

# Title

## Information

### About the author
2-4 sentences on who {post.author} is: role, affiliation, what they are known for, why their take on this topic matters. Be specific (companies, projects, prior work). Mark uncertainty if the handle is ambiguous.

### Post context
3-6 sentences explaining what the post is about, what it is responding to or referencing, why it matters now, and any surrounding debate or facts a reader needs. Cite concrete people, products, papers, or events.

### Original post
Quote the post verbatim.

## Sources

- https://source.example
- https://another.example

Rules:
- Always include the post URL itself in Sources.
- Include the author's primary profile or homepage in Sources when you can identify it.
- Do not invent facts. If you cannot verify the author, say so explicitly in "About the author".
- Do not add YAML frontmatter.
""".strip()
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty tweet enrichment")

        title, information, inline_sources = _parse_model_markdown(text)
        sources = list(
            dict.fromkeys(
                [post.url] + linked_urls + inline_sources + _grounding_sources(response)
            )
        )
        return ResearchDraft(title=title, information=information, sources=sources)

    def refine(
        self,
        current_markdown: str,
        recent_history: str,
        feedback: str,
        existing_sources: list[str],
    ) -> tuple[ResearchDraft, str]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc

        client = genai.Client(api_key=self.api_key)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool], temperature=0.2)
        prompt = f"""You are refining an existing research note based on user feedback.

Existing note (markdown):
---
{current_markdown}
---

Recent conversation:
{recent_history}

New user feedback to incorporate:
{feedback}

Return the FULL updated note in this exact structure:

# Title

## Information

Dense paragraphs and useful bullets, incorporating the user's feedback. Keep prior content unless the user asked to remove or correct it. Use Google Search grounding when the feedback asks for new facts. Include uncertainty when relevant.

## Sources

- https://source.example

After the closing of the markdown note, on a new line, write exactly:
SUMMARY: <one short sentence describing what changed in this revision>

Do not add YAML frontmatter. Do not include unsupported speculation.
"""
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty refinement")

        summary_match = re.search(r"^SUMMARY:\s*(.+)$", text, re.MULTILINE)
        if summary_match:
            summary = summary_match.group(1).strip()
            body = text[: summary_match.start()].rstrip()
        else:
            summary = "Note updated."
            body = text

        title, information, inline_sources = _parse_model_markdown(body)
        sources = list(
            dict.fromkeys(existing_sources + inline_sources + _grounding_sources(response))
        )
        if not sources:
            sources = list(existing_sources)
        return ResearchDraft(title=title, information=information, sources=sources), summary


def tweet_to_draft(post: TweetPost) -> ResearchDraft:
    info = [
        "X/Twitter post captured from the exact submitted status URL.",
        "",
        f"Author: {post.author}",
        f"Created at: {post.created_at}",
        "",
        "Post text:",
        "",
        post.text.strip(),
    ]
    links = _payload_links(post.source_payload)
    if links:
        info.extend(["", "Linked or media URLs:", ""])
        info.extend(f"- {link}" for link in links)
    return ResearchDraft(
        title=_tweet_title(post),
        information="\n".join(info).strip(),
        sources=list(dict.fromkeys([post.url] + links)),
    )


def smoke_test(config: ResearchConfig) -> dict[str, bool]:
    results = {
        "gemini": False,
        "apify": False,
        "langsmith": False,
    }
    if config.gemini_api_key:
        try:
            response = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": config.gemini_api_key},
                timeout=20,
            )
            results["gemini"] = response.ok
        except requests.RequestException:
            results["gemini"] = False
    if config.apify_api_token:
        try:
            response = requests.get(
                "https://api.apify.com/v2/users/me",
                headers={"Authorization": f"Bearer {config.apify_api_token}"},
                timeout=20,
            )
            results["apify"] = response.ok
        except requests.RequestException:
            results["apify"] = False
    import os

    endpoint = (os.environ.get("LANGSMITH_ENDPOINT") or os.environ.get("LANGCHAIN_ENDPOINT") or "").rstrip("/")
    key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if endpoint and key:
        try:
            response = requests.get(f"{endpoint}/info", headers={"x-api-key": key}, timeout=20)
            results["langsmith"] = response.ok
        except requests.RequestException:
            results["langsmith"] = False
    return results


def _gemini_prompt(submission: str, route: str, source_urls: list[str]) -> str:
    sources = "\n".join(f"- {url}" for url in source_urls) or "- No submitted URL."
    return f"""
You are the Researcher for a personal second brain.

Create a dense, source-backed Markdown note for the Organizer.
Route: {route}
Submitted item:
{submission}

Submitted source URLs:
{sources}

Return exactly this structure:

# Title

## Information

Dense paragraphs and useful bullets. Include uncertainty when relevant.

## Sources

- https://source.example

Do not add YAML frontmatter. Do not include unsupported speculation.
""".strip()


def _parse_model_markdown(text: str) -> tuple[str, str, list[str]]:
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    info_match = re.search(r"^##\s+Information\s*$", text, re.MULTILINE)
    sources_match = re.search(r"^##\s+Sources\s*$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Research Note"
    if info_match and sources_match and info_match.end() < sources_match.start():
        information = text[info_match.end() : sources_match.start()].strip()
        sources_text = text[sources_match.end() :].strip()
    else:
        information = re.sub(r"^#\s+.+$", "", text, count=1, flags=re.MULTILINE).strip()
        sources_text = text
    sources = re.findall(r"https?://[^\s)>]+", sources_text)
    return title, information or text, [source.rstrip(".,;") for source in sources]


def _grounding_sources(response: Any) -> list[str]:
    sources: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        metadata = getattr(candidate, "grounding_metadata", None) or getattr(candidate, "groundingMetadata", None)
        chunks = getattr(metadata, "grounding_chunks", None) or getattr(metadata, "groundingChunks", None) or []
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None) if web is not None else None
            if not uri and isinstance(chunk, dict):
                uri = ((chunk.get("web") or {}).get("uri"))
            if uri:
                sources.append(str(uri))
    return list(dict.fromkeys(sources))


def _payload_links(payload: dict[str, Any]) -> list[str]:
    text = json.dumps(payload, ensure_ascii=True)
    links = re.findall(r"https?://[^\s\"\\]+", text)
    return [link.rstrip(".,;") for link in list(dict.fromkeys(links))]


def _first_string(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (str, int)):
            return str(value)
    return ""


def _author_name(item: dict[str, Any]) -> str:
    author = item.get("author") or item.get("user")
    if isinstance(author, dict):
        return _first_string(author, ["userName", "username", "screenName", "name"])
    return _first_string(item, ["author", "username", "userName"])


def _tweet_matches(url: str, item_id: str, expected_status_id: str) -> bool:
    if item_id == expected_status_id:
        return True
    return bool(url and f"/status/{expected_status_id}" in url)


def _tweet_title(post: TweetPost) -> str:
    snippet = re.sub(r"\s+", " ", post.text).strip()
    if len(snippet) > 60:
        snippet = snippet[:57].rstrip() + "..."
    return f"X Post by {post.author}: {snippet}" if snippet else f"X Post by {post.author}"
