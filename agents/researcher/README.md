# Researcher

The Researcher receives Telegram submissions, enriches them when useful, and
writes information-dense Markdown files into the shared `input/` directory.

Routes:

- X/Twitter status URLs use the `apidojo/tweet-scraper` Apify actor and keep
  only the exact linked post/comment.
- General URLs, topics, concepts, names, and questions use Gemini with Google
  Search grounding.
- Personal notes are preserved without web lookup.

The Telegram webhook acknowledges messages immediately and runs research in a
background task. Local trace events are written to `runs/researcher_trace.jsonl`.
