# Source: Intelligence vs Agency

## Input

- [2026-05-01-intelligence-vs-agency-karpathy.md](../../input/2026-05-01-intelligence-vs-agency-karpathy.md)

## Compiled Into

- [Intelligence vs Agency](../concepts/intelligence-vs-agency.md)

## Information

Intelligence and agency are related but different concepts. Intelligence is the capacity to understand, model, reason, generate, predict, and compress patterns. Agency is the capacity to pursue goals through time by selecting actions, using tools, maintaining state, reacting to feedback, and correcting course. A system can be intelligent without being very agentic, and a system can show limited agency with relatively narrow intelligence if the environment, goals, and action space are tightly constrained.

This distinction is central to current LLM systems. A frontier model may produce excellent local answers, plans, or code edits while still failing as an autonomous worker. Agency requires more than a strong next-token predictor: it needs memory, tool access, planning, evaluation, permissions, monitoring, rollback, process control, and a way to notice when it is stuck or wrong. The gap between "the model can answer this" and "the system can reliably do this" is the gap between intelligence and agency.

Andrej Karpathy has repeatedly emphasized a sober view of current LLM agents and agentic coding. His public comments often treat LLMs as powerful but ghost-like intelligences that need scaffolding, supervision, and better interfaces before they become dependable long-horizon workers. In coding tools, for example, "agent mode" can mean anything from autocomplete with file edits to an autonomous loop that plans, modifies files, runs tests, and iterates. The model's raw ability is only one part of the final agent behavior.

For this project, the concept should become a design principle: Organizer should not be treated as a magical autonomous researcher just because the underlying model is smart. It should be treated as a compiler with explicit stages and checks. The closed loop needs durable inputs, structured outputs, run logs, evaluators, source traceability, and exit criteria. The system should measure whether the agent represented every input, cited claims, merged duplicates, preserved uncertainty, and improved the wiki without corrupting it.

Useful distinctions:

- Intelligence: understanding, reasoning, synthesis, pattern recognition, language generation.
- Agency: goal pursuit, action selection, tool use, persistence, state, recovery, feedback loops.
- Autonomy: how much the system can act without direct human steering.
- Reliability: how often the system does the right thing under messy conditions.
- Scaffolding: external structure that turns model capability into usable agency.

Brain links that should probably exist later: `concepts/intelligence-vs-agency.md`, `concepts/agentic-ai.md`, `concepts/llm-scaffolding.md`, `people/andrej-karpathy.md`, `topics/ai-agents.md`.

## Source URLs

- https://tweetlook.com/karpathy
- https://www.itpro.com/technology/artificial-intelligence/agentic-ai-hype-openai-andrej-karpathy
- https://blockchain.news/ainews/andrej-karpathy-discusses-agi-timelines-llm-agents-and-ai-industry-trends-2024
- https://agent-wars.com/news/2026-03-15-andrej-karpathy-agentic-ide
