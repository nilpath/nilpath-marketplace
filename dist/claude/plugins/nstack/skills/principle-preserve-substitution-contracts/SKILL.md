---
name: principle-preserve-substitution-contracts
description: Apply when adding or replacing an implementation behind an established contract. Preserve the caller-visible behavior, including inputs, results, invariants, errors, and observable effects.
disable-model-invocation: true
---

# Preserve Substitution Contracts

**Liskov Substitution Principle (LSP).** An implementation can replace another only when callers can keep relying on the established contract. Matching a type signature is not enough.

Preserve accepted inputs, promised results, invariants, errors, and observable effects. Do not strengthen preconditions. Do not weaken postconditions. A replacement must not make callers provide more, handle less favorable results, or lose effects they could observe before.

Use shared caller-visible examples to check the documented contract. For each documented input, verify the results, invariants, allowed errors, and observable effects. Permit differences that the contract allows, such as generated IDs, timestamps, or nondeterministic ordering. Do not require literal equality or clone implementation accidents.

Ask:

- Which inputs do callers currently rely on being accepted?
- Which results, errors, and effects can callers observe?
- Which invariants must hold before and after every operation?
- Does each shared example meet the documented results, invariants, allowed errors, and effects?
