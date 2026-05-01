# Agent Frameworks and Elixir/OTP

## Information

The article "Your Agent Framework Is Just a Bad Clone of Elixir: Concurrency Lessons from Telecom to AI" argues that many modern AI agent frameworks are rediscovering runtime ideas that the Erlang/Elixir ecosystem has treated as normal for decades. The core thesis is that production agent systems are not just prompt chains; they are concurrent, fault-prone, long-running distributed systems.

The Erlang/OTP and Elixir tradition was shaped by telecom systems that needed to run continuously, tolerate failures, isolate processes, pass messages, restart failed components, and remain observable. That world produced concepts such as lightweight processes, actor-style isolation, supervision trees, "let it crash" fault recovery, message passing, process registries, hot code upgrades, and runtime introspection.

The article criticizes Python and JavaScript/TypeScript agent stacks when they treat orchestration as a set of loosely connected function calls or graph nodes without mature runtime guarantees. For small demos this is fine. For long-running agents, the system needs failure isolation, retries, state ownership, backpressure, timeouts, observability, durable logs, and clear recovery behavior.

The article is directly relevant to this project because Organizer is planned as a closed-loop compiler with sub-agents. A robust version should not simply call a model repeatedly. It should treat Curator, Synthesizer, Critic, and Archivist as roles with contracts. Their outputs should be persisted, inspected, and evaluated. If one role fails, the system should report that failure rather than corrupting the brain.

Agent architecture lessons:

- Separate responsibilities between agents.
- Make state explicit and durable.
- Treat failures as expected events.
- Keep raw inputs recoverable.
- Write run reports.
- Make evaluator output inspectable.
- Use retries and max loop counts.
- Avoid infinite critique loops.
- Preserve source traceability.
- Prefer deterministic file boundaries where possible.

This article connects to design patterns, Murphy's Law, intelligence vs agency, self-hosting, and the idea that agency requires infrastructure around model intelligence.

## Source Trace

- Input file: [2026-05-01-agent-frameworks-elixir.md](../../input/2026-05-01-agent-frameworks-elixir.md)
- Source summary: [source summary](../sources/2026-05-01-agent-frameworks-elixir.md)

## Sources

- https://georgeguimaraes.com/your-agent-orchestrator-is-just-a-bad-clone-of-elixir/
- https://elixir-lang.org/
- https://www.erlang.org/doc/
- https://langchain-ai.github.io/langgraph/

## Related

- [Intelligence vs Agency](../concepts/intelligence-vs-agency.md)
- [Design Patterns](../concepts/design-patterns.md)
- [Lei de Murphy](../concepts/lei-de-murphy.md)
- [Self-Hosting](../concepts/self-hosting.md)
