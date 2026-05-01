# Lei de Murphy

## Information

Lei de Murphy is the Portuguese name for Murphy's Law. The common formulation is: if something can go wrong, it will go wrong. The phrase is usually humorous, but its practical value is as an engineering heuristic. It encourages designers to assume failure modes exist and to build systems that remain understandable and recoverable when failures happen.

Murphy's Law is not a scientific law. It is a reminder about complexity, fragility, hidden assumptions, and the difference between happy-path demos and real-world operation. In engineering, it points toward redundancy, validation, retries, monitoring, observability, backups, graceful degradation, permission boundaries, and rollback strategies.

In agent systems, Murphy's Law is especially relevant. An LLM agent may ignore part of an instruction, hallucinate a source, overfit to one document, miss a contradiction, call the wrong tool, produce an inconsistent file structure, or appear confident while being wrong. A good system assumes these failures are possible. The closed loop should include explicit checks rather than relying on vibes.

Useful applications to this project:

- Every run should produce a report.
- Every claim in the brain should be traceable.
- The agent should preserve uncertainty instead of forcing false certainty.
- Evaluators should check for orphan pages, duplicate concepts, missing citations, and ignored inputs.
- Raw input files should stay immutable or at least recoverable.
- The compiler should avoid silently deleting information.
- Failures should be visible in `runs/`, not hidden.

Related concepts include defensive design, pre-mortems, failure modes, observability, reliability engineering, Hanlon's razor, and "trust but verify" workflows.

## Source Trace

- Input file: [2026-05-01-lei-de-murphy.md](../../input/2026-05-01-lei-de-murphy.md)
- Source summary: [source summary](../sources/2026-05-01-lei-de-murphy.md)

## Sources

- https://www.britannica.com/dictionary/murphy
- https://en.wikipedia.org/wiki/Murphy%27s_law
- https://www.britannica.com/topic/Hanlons-razor

## Related

- [Agent Frameworks and Elixir/OTP](../topics/agent-frameworks-and-elixir-otp.md)
- [Self-Hosting](self-hosting.md)
