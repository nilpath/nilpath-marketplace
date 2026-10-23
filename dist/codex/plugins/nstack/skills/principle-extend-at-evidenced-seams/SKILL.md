---
name: principle-extend-at-evidenced-seams
description: Apply when you add a required variant or decide whether code needs an extension point. Base the choice on known requirements or a concrete testing need.
---

# Extend at evidenced seams

**Anticipation of change.** Add flexibility only when you can identify what must vary. Evidence can be existing variants, a requirement known to change, or a concrete testing need. Do not add extension points for hypothetical requirements.

**Open/closed principle, OCP.** Choose the change that fits the code:

1. If an existing extension point supports the required contract, add an implementation.
2. If the model has a closed set of variants, change the model and handle every variant.
3. If the contract must change, redesign the extension point.

OCP does not forbid editing existing code.

An extension point can have one implementation without an interface wrapper. It must still represent a real boundary or variation.

Ask:

- What requirement or test justifies this extension point?
- Does an existing extension point support the required contract?
- If the variant set is closed, where does the code handle each variant?
- Does the requirement change the contract itself?
