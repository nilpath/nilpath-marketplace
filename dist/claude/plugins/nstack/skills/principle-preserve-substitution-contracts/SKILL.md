---
name: principle-preserve-substitution-contracts
description: Apply when you add or replace an implementation of an existing contract. Preserve the inputs, results, invariants, errors, and effects that callers rely on.
disable-model-invocation: true
---

# Preserve substitution contracts

**Liskov substitution principle, LSP.** Callers must be able to use a replacement under the same contract. A matching type signature is not enough.

Preserve the contract's accepted inputs, promised results, invariants, errors, and observable effects. Do not strengthen preconditions or weaken postconditions.

Run the same caller-visible examples against each implementation. For each documented input, check the results, invariants, errors, and effects against the contract. Allow differences the contract permits, such as generated IDs, timestamps, or nondeterministic ordering. Do not copy details of the old implementation that the contract does not promise.

Ask:

- Which inputs must callers still be able to pass?
- Which results, errors, and effects do callers rely on?
- Which invariants must hold before and after every operation?
- Does every implementation pass the same contract tests?
