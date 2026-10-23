---
name: principle-extend-at-evidenced-seams
description: Apply when adding demonstrated variation or deciding whether to introduce an extension point. Extend earned seams, update closed variants exhaustively, and redesign contracts that changed.
---

# Extend at Evidenced Seams

**Anticipation of Change.** Introduce flexibility only when variation is demonstrated. Evidence can be real variants, a requirement known to change, or a genuine testing boundary. Do not add an extension point for hypothetical flexibility.

**Open/Closed Principle (OCP).** Choose the change that fits the current domain:

1. For an established open seam, add an implementation when its contract fits.
2. For a closed variant set, edit the model and handle every variant exhaustively.
3. When the contract itself changes, redesign the seam instead of forcing the requirement through an unsuitable extension point.

Open and closed guidance does not prohibit all edits to existing code. An existing model can be the right place to change when it is closed and its variants remain explicit.

Do not require an interface wrapper or two concrete implementations before a seam earns its cost. Require evidence that the seam represents a real boundary or variation.

Ask:

- What demonstrated variation or testing boundary earns flexibility here?
- Does an existing seam accept the required contract without distortion?
- If the model is closed, where will every variant be handled?
- Has the contract changed enough that the seam needs redesign?
