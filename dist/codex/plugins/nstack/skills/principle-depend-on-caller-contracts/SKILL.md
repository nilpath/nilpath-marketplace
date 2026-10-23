---
name: principle-depend-on-caller-contracts
description: Apply when you design a dependency or interface, or call through a collaborator to reach another object.
---

# Depend on caller contracts

**Interface segregation principle, ISP.** Limit the contract to operations the caller needs. Do not require methods that an implementation cannot support. Do not expose implementation details that callers do not need.

**Law of Demeter.** Use the collaborator's own operations instead of reaching through its internal objects. Put the needed operation on the collaborator when it can hide the internal calls.

**Dependency inversion principle, DIP.** Policy code should depend on the caller's contract, not the concrete implementation. Choose implementations where the application connects its dependencies, then pass them to policy code. Do not introduce dependency cycles.

If coupling makes the code hard to test, review its dependencies. That alone does not justify a new contract.

Reuse existing functions and types when they already fit. Before adding a contract, name the dependency problem it fixes, the components it lets you combine, or the test it supports. A contract can be useful with one implementation. Do not add wrappers by default.

Ask:

- Which operations does the caller need from this collaborator?
- Which methods would implementations leave empty or reject?
- Where should the application choose the concrete implementation?
- Does the proposed dependency introduce a cycle?
- Which dependencies make the code hard to test?
