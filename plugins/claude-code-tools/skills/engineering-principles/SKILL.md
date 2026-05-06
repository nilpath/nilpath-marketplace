---
name: engineering-principles
description: Core software engineering and design principles for writing production-quality code. Use as a reference when making design decisions, reviewing code, or when principled guidance is needed on modularity, abstraction, encapsulation, SOLID, DRY, KISS, YAGNI, and other foundational practices.
argument-hint: '<context> (e.g., "reviewing a refactor", "designing a new module", "choosing between approaches")'
---

# Engineering Principles

A reference for the core software engineering principles that govern how code is designed, structured, and maintained. These principles are language-agnostic and apply universally.

## Core Principles

### Modularity

Each component has a single, well-defined responsibility. When you create or modify a module, ask: "Does this do exactly one thing? Could I replace it without touching its neighbors?" If a file grows beyond a coherent responsibility, split it.

### Abstraction

Expose intent, hide mechanism. Public interfaces describe *what*, not *how*. When reviewing your code, ask: "Could someone use this without reading the implementation?" If not, your interface leaks.

### Encapsulation

Data and the operations on that data belong together. Do not scatter related state across files. Do not expose internal fields that callers should not depend on. Use access boundaries — private members, module-scoped functions, closures — to enforce this.

### Separation of Concerns

UI logic does not contain business rules. Business rules do not contain transport details. Data access does not contain presentation formatting. When you catch yourself mixing concerns, stop and restructure before continuing.

### Anticipation of Change

Design for the change that is *likely*, not the change that is *possible*. Use interfaces and dependency injection at natural seam points. Do not over-abstract — a point of flexibility costs complexity, so place them deliberately where requirements are known to vary.

## Key Development Principles

### DRY (Don't Repeat Yourself)

When you see the same logic in two places, extract it — but only if the duplication is *conceptual*, not merely textual. Two blocks of code that look similar but evolve independently are not duplication. True duplication means a bug fix in one place must also be applied in the other.

### KISS (Keep It Simple, Stupid)

Prefer the straightforward solution. A clever one-liner that requires a comment to explain is worse than three obvious lines. Complexity is a cost; justify every unit of it.

### YAGNI (You Aren't Gonna Need It)

Implement what is needed now. Do not build extension points, configuration options, or abstractions for hypothetical future requirements. When the future arrives, you will know more and can build the right thing then.

### SOLID Principles

- **Single Responsibility:** A class/module has one reason to change.
- **Open/Closed:** Extend behavior through composition or new implementations, not by modifying existing code.
- **Liskov Substitution:** Subtypes must be substitutable for their base types without breaking correctness.
- **Interface Segregation:** Depend on narrow, specific interfaces — not broad ones that force implementations to stub out methods they don't need.
- **Dependency Inversion:** High-level policy depends on abstractions, not on low-level details. Inject dependencies rather than importing concrete implementations at the call site.

### Law of Demeter

An object should only talk to its immediate collaborators. Avoid chaining through objects: `a.getB().getC().doThing()` couples you to the entire chain. Instead, ask `a` to do what you need, and let `a` delegate internally.

## Applying These Principles

### When Designing a New Module

1. Define the public interface first — what does the caller need?
2. Identify the single responsibility — if you cannot state it in one sentence, split
3. List the dependencies — are they abstractions or concrete implementations?
4. Consider what is likely to change — place flexibility at those seams, not everywhere

### When Modifying Existing Code

1. Understand the existing design before changing it
2. Respect existing module boundaries — do not leak concerns across them
3. If the existing design conflicts with the change, refactor the design first in a separate step
4. Do not mix refactoring with feature work in the same change

### When Reviewing Code

Ask these questions:

- Does each module have a single, clear responsibility?
- Are implementation details hidden behind clean interfaces?
- Could I change one module without rippling changes through its neighbors?
- Is there genuine duplication, or just superficial similarity?
- Is every abstraction earning its complexity cost?
- Are dependencies flowing in one direction, without cycles?

### Red Flags

- A module that imports from many unrelated modules — likely doing too much
- A function that takes many parameters — likely has multiple responsibilities
- A change that requires editing many files — likely boundaries are wrong
- A piece of code that is hard to test — likely too coupled or doing too much
- A name that does not communicate intent — likely the design is unclear
