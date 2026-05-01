# Personal LLM Wiki Agent

## Summary

This project is a personal second brain that grows from things sent over Telegram: links, names, concepts, questions, notes, and other fragments worth remembering or researching.

Agent 1 receives submissions through Telegram, enriches them when useful, and saves each item as a Markdown file in an append-only input directory. Agent 2 periodically compiles those raw inputs into a curated Markdown knowledge base inspired by Karpathy's LLM Wiki pattern: raw sources stay intact, while the wiki is continuously reorganized, cross-linked, linted, and improved by agents.

The goal is not just to store links. The goal is to turn a stream of interesting inputs into a useful, source-backed personal knowledge base.

## Product Goals

- Capture interesting material with minimal friction from Telegram.
- Accept all submitted items without filtering at ingestion time.
- Support common personal research sources:
  - `x.com` posts and threads
  - news articles
  - YouTube videos
  - general web pages
- Support free-form inputs:
  - names of people
  - companies and products
  - concepts
  - questions
  - rough notes
  - topics to research later
- Preserve raw inputs as immutable Markdown files.
- Compile raw inputs into a structured second brain.
- Improve the second brain through a closed-loop agent process with evaluator sub-agents.
- Produce a clear hackathon demo that shows ingestion, compilation, quality checks, and final wiki updates.

## Non-Goals

- Multi-user collaboration.
- Complex frontend application.
- Full Obsidian plugin or browser extension.
- Perfect extraction for every website.
- Vector database or RAG-first architecture.
- Manual curation UI.

## Architecture

```txt
Telegram
   |
   v
Agent 1: Ingestion Bot
   |
   v
input/
   |
   v
Agent 2: Wiki Compiler
   |
   v
brain/
   |
   v
runs/
```

The system is file-first. Markdown files are the main interface between agents, the user, and the demo.

## Directory Structure

```txt
.
├── input/
│   ├── 2026-05-01-example-news-article.md
│   ├── 2026-05-01-example-x-thread.md
│   ├── 2026-05-01-example-concept.md
│   └── 2026-05-01-existing-doc.md
├── brain/
│   ├── README.md
│   ├── schema.md
│   ├── index.md
│   ├── open_questions.md
│   ├── changelog.md
│   ├── topics/
│   ├── people/
│   ├── companies/
│   ├── projects/
│   ├── concepts/
│   └── sources/
├── runs/
│   └── latest_report.md
├── config/
│   ├── quality_criteria.md
│   └── prompts/
└── SPEC.md
```

## Agent 1: Telegram Ingestion Bot

Agent 1 is responsible for receiving Telegram submissions and converting them into raw Markdown inputs.

### Interface

- Runs as a Telegram bot.
- Receives Telegram updates through HTTP.
- Uses a Cloudflare Tunnel to expose the local webhook during development and demo.
- Accepts any text sent by the user.

### Supported Input Types

- `x.com` URLs
- News article URLs
- YouTube video URLs
- General web URLs
- Names of people
- Company, product, or project names
- Concepts and topics
- Questions
- Rough notes

### Ingestion Behavior

For every submitted item, Agent 1 should:

1. Accept the item.
2. Classify it lightly as a URL, name, concept, question, note, or unknown item.
3. Fetch or extract useful content where possible.
4. For non-URL items, preserve the raw text and optionally add brief lookup or interpretation notes.
5. Save a Markdown file in `input/`.
6. Include the submitted text clearly.
7. Avoid making deep curation decisions.
8. Reply on Telegram with a short confirmation.

### Raw Input Markdown Format

The raw input files should stay simple. No YAML frontmatter is required for the MVP.

```md
# Submission

https://example.com/article

# Content

Extracted article text, transcript, tweet text, or best-effort content goes here.

# Notes

Optional extraction notes, errors, or context from the ingestion agent.
```

For a non-URL input:

```md
# Submission

Geoffrey Hinton

# Content

The user submitted a person name for later research or integration into the second brain.

# Notes

Input type: person/name.
```

If extraction fails, the file should still be saved:

```md
# Submission

https://example.com/article

# Content

Extraction failed.

# Notes

Reason: paywall, unsupported page, timeout, unavailable transcript, lookup failed, or other error.
```

## Agent 2: Wiki Compiler

Agent 2 periodically reads all Markdown files in `input/` and updates the second brain in `brain/`.

It should behave like a compiler, not a chatbot:

- raw source files are inputs
- the Markdown wiki is the compiled output
- quality checks are the test suite
- each run produces an audit report

### Runtime

- Uses LangChain Deep Agents SDK.
- Uses Gemini Flash for development.
- Runs periodically during the demo.
- Can also be triggered manually for testing.

### Compiler Loop

Each run should:

1. Read all files in `input/`, including any existing documents already present before the latest Telegram message.
2. Inspect the current `brain/` state.
3. Decide which pages need to be created or updated.
4. Update the brain.
5. Run evaluator sub-agents.
6. Apply improvements.
7. Repeat until quality criteria are met or the maximum loop count is reached.
8. Write a run report to `runs/latest_report.md`.

### Suggested Max Loop Count

For hackathon reliability:

- MVP: 2 evaluator/improvement passes
- Stretch: 3-5 passes with stricter convergence checks

## Brain Structure

The second brain should be a Markdown wiki.

### Core Files

`brain/README.md`
: Explains what the brain contains and how it is organized.

`brain/schema.md`
: Defines page conventions, linking rules, citation expectations, and quality criteria.

`brain/index.md`
: Main navigation page across topics, people, companies, concepts, projects, and sources.

`brain/open_questions.md`
: Unresolved questions, contradictions, weak claims, and research gaps.

`brain/changelog.md`
: Human-readable log of each compiler run and what changed.

### Entity Folders

`brain/topics/`
: Broad areas of interest.

`brain/concepts/`
: Reusable ideas, patterns, techniques, and mental models.

`brain/people/`
: People mentioned in sources.

`brain/companies/`
: Companies and organizations.

`brain/projects/`
: Products, repositories, tools, and initiatives.

`brain/sources/`
: Source-level summaries and references back to raw input files.

## Source Traceability

Every meaningful claim in the brain should be traceable to a source.

For the MVP, citations can be simple Markdown links to source pages or raw input files:

```md
Gemini Flash is used as the development model for this project. See [source](../sources/example-source.md).
```

The system should avoid inventing unsupported claims. If a claim is useful but uncertain, it should be marked as uncertain or moved to `open_questions.md`.

## Sub-Agents

Agent 2 should use specialized sub-agents inside its closed loop.

### Curator

Decides where new information belongs.

Responsibilities:

- Identify topics, concepts, people, companies, and projects.
- Decide whether to create new pages or update existing ones.
- Detect likely duplicates.

### Synthesizer

Turns raw source material into durable wiki content.

Responsibilities:

- Update topic and concept pages.
- Merge overlapping information.
- Write concise, useful summaries.
- Preserve links to sources.

### Critic

Evaluates the quality of the brain.

Responsibilities:

- Find missing citations.
- Detect weak or unsupported claims.
- Identify contradictions.
- Identify duplicate pages.
- Check whether important source material was ignored.

### Archivist

Maintains navigation and auditability.

Responsibilities:

- Update `index.md`.
- Update backlinks and cross-links.
- Update `changelog.md`.
- Maintain source summaries in `sources/`.
- Write run reports.

## Quality Criteria

The compiler loop should continue until these criteria are met or the max loop count is reached:

- Every input file is represented somewhere in `brain/`.
- Every source has a corresponding source summary.
- No important source is silently ignored.
- No orphan pages exist in the main brain structure.
- New pages are linked from `index.md` or another discoverable page.
- Topic and concept pages include useful cross-links.
- Meaningful claims link back to source material.
- Duplicate concepts are merged or explicitly distinguished.
- Contradictions and weak claims are listed in `open_questions.md`.
- `changelog.md` explains what changed during the run.
- `runs/latest_report.md` includes pass/fail status for quality checks.

## Run Report Format

Each Agent 2 run should write:

```md
# Run Report

Date: 2026-05-01

## Inputs Processed

- input/example-1.md
- input/example-2.md

## Pages Created

- brain/topics/example-topic.md

## Pages Updated

- brain/index.md
- brain/changelog.md

## Quality Checks

- [x] Every input represented
- [x] Source summaries created
- [x] Index updated
- [ ] Some claims need stronger citation

## Open Issues

- Add stronger source support for ...

## Final Status

Passed with warnings.
```

## Hackathon Demo Flow

The demo should show the system handling both a new Telegram submission and an existing input document.

### Before Demo

Prepare:

- One existing Markdown file already in `input/`.
- An initialized `brain/` with either no content or a small existing wiki.
- Telegram bot running locally.
- Cloudflare Tunnel connected to the bot webhook.
- Agent 2 ready to run manually or on a short interval.

### Demo Steps

1. Show `input/` already contains one document.
2. Send a new item to the Telegram bot. This can be a URL, name, concept, or question.
3. Show Agent 1 creates a new Markdown file in `input/`.
4. Trigger Agent 2.
5. Show Agent 2 reads both:
   - the existing input document
   - the new Telegram-created document
6. Show `brain/` being updated.
7. Show `brain/changelog.md`.
8. Show `runs/latest_report.md`.
9. Ask a question against the brain and show a source-backed answer.

## Example Demo Inputs

Use one existing document and one live Telegram submission.

Good existing input examples:

- a short Markdown note about the user's current research interests
- a saved article about agents
- a YouTube transcript about personal knowledge systems
- an `x.com` thread about LLM Wikis

Good live Telegram examples:

- a fresh news article
- a YouTube video with transcript
- an `x.com` thread
- a person's name
- a concept to research
- a question to integrate into the brain

## Technology Stack

- Python
- LangChain Deep Agents SDK
- Gemini Flash during development
- Telegram Bot API
- Cloudflare Tunnel
- Markdown files as storage

## Open Decisions

- Exact scheduler mechanism for Agent 2.
- Whether processed input files should be marked externally or left fully immutable.
- Whether the brain should use Obsidian-style `[[wiki links]]` or plain Markdown links.
- Whether source extraction should use dedicated libraries per source type.
- Whether Telegram should support commands like `/run`, `/status`, and `/ask`.
- Whether Agent 2 should commit changes to Git after each successful run.

## MVP Acceptance Criteria

- A user can send a URL, name, concept, question, or note to Telegram.
- A Markdown file is created in `input/`.
- Agent 2 processes all files in `input/`, including pre-existing ones.
- Agent 2 creates or updates a Markdown second brain in `brain/`.
- Agent 2 runs at least one critique/improvement pass.
- The brain includes source traceability.
- A run report is written to `runs/latest_report.md`.
- The demo can show a before/after diff of the brain.
