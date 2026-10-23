---
name: principle-depend-on-caller-contracts
description: Apply when designing a collaborator dependency or contract, or when reaching through a collaborator's collaborators. Depend on the capabilities callers need, keep policy independent of mechanism, and avoid cycles.
---

# Depend on Caller Contracts

Define a collaborator by the capabilities its caller needs. Keep the contract narrow. Do not require irrelevant methods, force stub implementations, or expose implementation details that the caller does not need.

Ask an immediate collaborator for behavior. Do not traverse its private object graph to reach another object's data or methods. Move the needed behavior to the immediate collaborator when that hides the traversal.

Keep high-level policy independent of concrete mechanisms. Supply mechanisms at a composition boundary instead of constructing or importing concrete implementations throughout the policy. Keep dependency direction clear and avoid cycles. Treat hard-to-test coupling as a signal to investigate the dependency, not automatic proof that a new contract is needed.

Reuse adequate existing functions and types. Add a contract only when it creates a concrete dependency, composition, or testing benefit. A useful contract can have one implementation. Do not add wrappers by default.

Ask:

- What capability does this caller need from its immediate collaborator?
- Which methods would an implementation have to stub or ignore?
- Where can composition choose the mechanism without leaking it into policy?
- Does the proposed dependency introduce a cycle?
- Does hard-to-test coupling reveal a dependency worth investigating?
