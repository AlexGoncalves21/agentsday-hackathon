# Design Patterns

## Information

Design patterns are reusable solutions to recurring design problems. They are not finished code, libraries, or rigid templates. A pattern names a common problem, describes the forces and tradeoffs around it, and gives a reusable shape for a solution. Their value is partly technical and partly linguistic: they give teams a shared vocabulary for discussing structure.

The classic software design pattern tradition comes from the "Gang of Four" book, which organized 23 object-oriented patterns into three groups: creational, structural, and behavioral. Creational patterns deal with object creation, structural patterns deal with composition, and behavioral patterns deal with communication and responsibility between objects.

Classic examples:

- Creational: Factory Method, Abstract Factory, Builder, Prototype, Singleton.
- Structural: Adapter, Bridge, Composite, Decorator, Facade, Flyweight, Proxy.
- Behavioral: Chain of Responsibility, Command, Iterator, Mediator, Memento, Observer, State, Strategy, Template Method, Visitor.

Patterns are helpful when they reduce repeated design work, clarify tradeoffs, or make a system easier to reason about. They become harmful when applied mechanically, especially when the language or framework already provides a simpler idiom. Over-patterning can add ceremony, indirection, and needless abstraction.

In AI systems, "design patterns" increasingly refers to recurring agent architectures rather than only object-oriented structures. Examples include evaluator-optimizer loops, planner-executor loops, router agents, reflection loops, tool-use loops, supervisor agents, memory managers, retrieval-augmented generation, human-in-the-loop approval, and critic/repair cycles.

This project uses several agent design patterns:

- File-first architecture: Markdown files are the boundary between ingestion and compilation.
- Compiler pattern: raw inputs become a structured wiki.
- Evaluator-optimizer loop: Organizer writes, critiques, and repairs.
- Role decomposition: Curator, Synthesizer, Critic, and Archivist each optimize a different aspect.
- Audit log: `runs/latest_report.md` explains what happened.
- Source traceability: claims should link back to input files or source URLs.

Design patterns connect strongly to the Elixir/OTP article. Supervision trees, actor isolation, message passing, and restart strategies are mature patterns for concurrent systems and can inspire reliable agent orchestration.

## Sources

- https://refactoring.guru/design-patterns
- https://refactoring.guru/es/design-patterns
- https://www.coursera.org/articles/gang-of-four-design-patterns
- https://textbooks.cs.ksu.edu/cc410/i-oop/09-design-patterns/03-software-design-patterns/

