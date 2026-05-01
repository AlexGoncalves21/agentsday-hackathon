# Personal LLM Wiki Agent

## Summary

This project is a personal second brain that grows from things sent over Telegram: links, names, concepts, questions, notes, and other fragments worth remembering or researching.

The Researcher receives submissions through Telegram, enriches them when useful, and saves each item as a Markdown file in an append-only input directory. The Organizer periodically compiles those raw inputs into a curated Markdown knowledge base inspired by Karpathy's LLM Wiki pattern: raw sources stay intact, while the wiki is continuously reorganized, cross-linked, linted, and improved by agents.

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
- Complex manual curation UI.
- Full Obsidian plugin or browser extension.
- Perfect extraction for every website.
- Vector database or RAG-first architecture.
- Manual curation UI.

## Architecture

```txt
Telegram
   |
   v
Researcher: Ingestion Bot
   |
   v
input/
   |
   v
Organizer: Wiki Compiler
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
│   ├── graph.json
│   ├── graph_diff.json
│   ├── open_questions.md
│   ├── changelog.md
│   ├── topics/
│   ├── people/
│   ├── companies/
│   ├── projects/
│   ├── events/
│   ├── works/
│   ├── concepts/
│   └── sources/
├── runs/
│   └── latest_report.md
├── agents/
│   ├── researcher/
│   │   ├── README.md
│   │   └── prompts/
│   │       └── researcher.yaml
│   └── organizer/
│       ├── README.md
│       ├── config.yaml
│       ├── prompts/
│       │   └── organizer.yaml
│       ├── second_brain_agent/
│       └── tests/
├── frontend/
│   ├── package.json
│   └── src/
└── SPEC.md
```

## Code Organization

The implementation should follow normal modular code best practices. The goal is to make the hackathon build fast without creating a single hard-to-debug script.

Suggested module boundaries:

- Telegram ingestion and webhook handling.
- Content extraction and web lookup.
- Input Markdown writing.
- Organizer config loading.
- Input Markdown parsing.
- Brain planning.
- Brain writing.
- Evaluator passes.
- Run reporting.
- Deterministic graph artifact generation.

Prompts should live outside the code in YAML files:

- `agents/researcher/prompts/researcher.yaml` for Telegram ingestion, enrichment, and input Markdown generation.
- `agents/organizer/prompts/organizer.yaml` for second brain compilation, sub-agent roles, and evaluator instructions.

Code should load prompts from these files instead of hardcoding long prompt strings inside Python modules.

Each main agent should own its code, config, prompts, and tests inside its own directory under `agents/`. Shared product artifacts stay at the repo root:

- `input/` is the handoff directory written by Researcher and read by Organizer.
- `brain/` is the compiled second brain written by Organizer.
- `runs/` contains Organizer run reports.
- `frontend/` contains the graph UI and reads generated files from `brain/`.

## Researcher: Telegram Ingestion Bot

Researcher is responsible for receiving Telegram submissions and converting them into raw Markdown inputs.

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

For every submitted item, Researcher should:

1. Accept the item.
2. Classify it lightly as a URL, name, concept, question, note, or unknown item.
3. Fetch or extract useful content where possible.
4. For non-URL items, preserve the raw text and optionally add brief lookup or interpretation notes.
5. Save a Markdown file in `input/`.
6. Include the submitted text clearly.
7. Avoid making deep curation decisions.
8. Reply on Telegram with a short confirmation.

### Raw Input Markdown Format

The raw input files should stay simple, information-dense, and consistent. No YAML frontmatter is required for the MVP.

```md
# Title

Short human-readable title.

## Information

Dense extracted or researched information. This can mix paragraphs and bullet points.

Researcher should include enough context that Organizer can compile a useful second brain page without doing first-pass research again.

## Sources

- https://example.com/article
- https://example.com/another-source
```

For a non-URL input:

```md
# Geoffrey Hinton

## Information

Geoffrey Hinton is a computer scientist and cognitive psychologist known for foundational work in neural networks and deep learning.

Important related topics include backpropagation, neural networks, deep learning, AI safety, and the 2024 Nobel Prize in Physics.

## Sources

- https://www.nobelprize.org/
- https://en.wikipedia.org/wiki/Geoffrey_Hinton
```

If extraction fails, the file should still be saved:

```md
# Failed Extraction: Example Article

## Information

Researcher could not extract useful content from the submitted item.

Submitted item: https://example.com/article

Reason: paywall, unsupported page, timeout, unavailable transcript, lookup failed, or other error.

## Sources

- https://example.com/article
```

## Organizer: Wiki Compiler

Organizer periodically reads all Markdown files in `input/` and updates the second brain in `brain/`.

It should behave like a compiler, not a chatbot:

- raw source files are inputs
- the Markdown wiki is the compiled output
- quality checks are the test suite
- each run produces an audit report

### Runtime

- Uses LangChain Deep Agents SDK.
- Uses Gemini 3.0 Flash for development.
- Runs periodically during the demo.
- Can also be triggered manually for testing.
- Reads runtime behavior from `agents/organizer/config.yaml`.
- Reads prompt and sub-agent instructions from `agents/organizer/prompts/organizer.yaml`.

### CLI

Organizer should be runnable from the project root:

```bash
python3 -m agents.organizer.second_brain_agent validate-inputs
python3 -m agents.organizer.second_brain_agent run
```

The deterministic compiler path is the default development path. The LLM-backed Deep Agents path can be invoked explicitly once dependencies and Gemini credentials are available:

```bash
python3 -m agents.organizer.second_brain_agent run --use-llm
```

### Config

Organizer config should stay small. Quality expectations belong in this spec and in prompts, not in a large config tree.

```yaml
mode: dev

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview

loop:
  max_iterations: 3
```

### Run Modes

In `dev` mode:

- Organizer reads every Markdown file in `input/`.
- Organizer does not delete input files after processing.
- Organizer rebuilds `brain/` from scratch on every run.
- Organizer writes a fresh `runs/latest_report.md`.
- Organizer writes a fresh `runs/trace.jsonl`.
- Organizer writes sub-agent trace notes under `runs/subagents/`.
- Organizer does not use previous run reports as context.

This makes the compiler repeatable while prompts, schemas, and writer behavior are being tuned.

In future `prod` mode:

- Organizer can preserve `brain/` and update it incrementally.
- Organizer can archive or mark processed inputs.
- Organizer still writes run reports.
- Organizer should avoid rebuilding from scratch unless explicitly configured.

### Compiler Loop

Each run should:

1. Read all files in `input/`, including any existing documents already present before the latest Telegram message.
2. Parse each file according to the required title, information, and sources structure.
3. If running in `dev` mode, clear and rebuild `brain/` from scratch.
4. If running in future `prod` mode, inspect the current `brain/` state and update incrementally.
5. Decide which pages need to be created or updated.
6. Update the brain.
7. Run evaluator sub-agents.
8. Apply improvements.
9. Repeat until quality criteria are met or the maximum loop count is reached.
10. Generate the final `brain/index.md` after the Markdown pages are written.
11. Deterministically generate graph artifacts from the compiled Markdown links.
12. Write trace artifacts to `runs/trace.jsonl` and `runs/subagents/`.
13. Write a run report to `runs/latest_report.md`.

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

`brain/graph.json`
: Deterministic node and edge graph built from the compiled Markdown files.

`brain/graph_diff.json`
: Deterministic change summary comparing the current graph to the previous graph state.

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

`brain/events/`
: Historical events, battles, releases, incidents, and dated milestones.

`brain/works/`
: Books, essays, videos, fictional works, papers, and other authored artifacts.

`brain/sources/`
: Source-level summaries and references back to raw input files.

## Source Traceability

Every meaningful claim in the brain should be traceable to a source.

For the MVP, citations can be simple Markdown links to source pages or raw input files:

```md
Gemini 3.0 Flash is used as the development model for this project. See [source](../sources/example-source.md).
```

The system should avoid inventing unsupported claims. If a claim is useful but uncertain, it should be marked as uncertain or moved to `open_questions.md`.

## Sub-Agents

Organizer should use specialized sub-agents inside its closed loop.

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

## Graph Generation

The graph is generated by deterministic Python code, not by model tool calls. The Organizer writes the Markdown second brain first, then calls a separate graph module as a final build step.

Graph generation should:

- Create one node per Markdown file in `brain/`.
- Extract edges from internal Markdown links and supported wiki-style links.
- Write `brain/graph.json` for the UI.
- Write `brain/graph_diff.json` so the UI can highlight new or changed nodes and new links.
- Persist a small previous-state file so dev-mode rebuilds can still compare the new graph with the last run.
- Keep graph logic isolated from prompt logic and LLM-backed Organizer behavior.

## Frontend

The frontend is a small root-level Vite app under `frontend/`. It renders the generated graph artifacts and does not parse Markdown or call generative models.

The UI should:

- Load `brain/graph.json` and `brain/graph_diff.json`.
- Render concepts, people, sources, and other Markdown pages as a graph.
- Highlight nodes and connections added or changed since the user's previous UI visit.
- Let the user mark the current build as seen locally.
- Link selected nodes back to the corresponding Markdown file.

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

Each Organizer run should write:

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
- Organizer ready to run manually or on a short interval.

### Demo Steps

1. Show `input/` already contains one document.
2. Send a new item to the Telegram bot. This can be a URL, name, concept, or question.
3. Show Researcher creates a new Markdown file in `input/`.
4. Trigger Organizer.
5. Show Organizer reads both:
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

- Python 3.11+ for the LLM-backed Deep Agents path
- LangChain Deep Agents SDK
- Gemini 3.0 Flash during development
- Telegram Bot API
- Cloudflare Tunnel
- Markdown files as storage

## Open Decisions

- Exact scheduler mechanism for Organizer.
- Whether future prod mode should archive processed input files, mark them externally, or leave them fully immutable.
- Whether the brain should use Obsidian-style `[[wiki links]]` or plain Markdown links.
- Whether source extraction should use dedicated libraries per source type.
- Whether Telegram should support commands like `/run`, `/status`, and `/ask`.
- Whether Organizer should commit changes to Git after each successful run.

## MVP Acceptance Criteria

- A user can send a URL, name, concept, question, or note to Telegram.
- A Markdown file is created in `input/`.
- Organizer processes all files in `input/`, including pre-existing ones.
- In dev mode, Organizer rebuilds a Markdown second brain in `brain/` from scratch.
- Organizer runs at least one critique/improvement pass.
- The brain includes source traceability.
- A run report is written to `runs/latest_report.md`.
- The demo can show a before/after diff of the brain.
