---
name: principle-depend-on-caller-contracts
description: Apply when designing a collaborator dependency or contract, or when reaching through a collaborator's collaborators. Depend on the capabilities callers need, keep policy independent of mechanism, and avoid cycles.
disable-model-invocation: true
---

# Depend on Caller Contracts

Define a collaborator by the capabilities its caller needs. Keep the contract narrow. Do not require irrelevant methods, force stub implementations, or expose implementation details that the caller does not need.

Ask an immediate collaborator for behavior. Do not traverse its private object graph to reach another object's data or methods. Move the needed behavior to the immediate collaborator when that hides the traversal.

Keep high-level policy independent of concrete mechanisms. Supply mechanisms at a composition boundary instead of constructing or importing concrete implementations throughout the policy. Keep dependency direction clear and avoid cycles.

Do not add an interface wrapper for every dependency. Add a contract when it removes a real caller dependency, enables a useful composition boundary, or states a behavior that callers need.

Ask:

- What capability does this caller need from its immediate collaborator?
- Which methods would an implementation have to stub or ignore?
- Where can composition choose the mechanism without leaking it into policy?
- Does the proposed dependency introduce a cycle?
