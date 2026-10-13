# Core Principles

Core principles guide skill authoring decisions. These ensure skills are efficient, effective, and maintainable across different models and use cases.

## Markdown Structure Principle

Skills use **standard markdown headings** for body structure. No XML tags.

```markdown
---
name: my-skill
description: What it does and when to use it
---

# My Skill Name

## Quick Start
Immediate actionable guidance...

## Instructions
Step-by-step procedures...

## Examples
Concrete examples...
```

Keep markdown formatting within content (bold, italic, lists, code blocks, links). The skill body is standard markdown from top to bottom.

**Why not XML?**

This guide uses Markdown headings as its authoring convention. They make instructions readable by humans and agents without requiring a custom tag vocabulary.

**Common body sections** (use what fits your skill):

| Section heading | Purpose |
|----------------|---------|
| `## Quick Start` | Fastest path to value — working example |
| `## Instructions` | Core step-by-step guidance |
| `## Examples` | Input/output pairs |
| `## Advanced` | Deep-dive topics, link to reference files |
| `## Guidelines` | Rules and constraints |
| `## Troubleshooting` | Common failure modes |

## Conciseness Principle

The context window is shared. Your skill shares it with the system prompt, conversation history, other skills' metadata, and the actual request.

Only add context the agent doesn't already have. Challenge each piece of information:
- "Does the agent really need this explanation?"
- "Can I assume the model knows this?"
- "Does this paragraph justify its token cost?"

Assume the model is capable. Don't explain obvious concepts.

**Concise** (~50 tokens):

````markdown
## Quick Start

Extract PDF text with pdfplumber:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
````

**Verbose** (~150 tokens, same information):

```markdown
## Quick Start

PDF files are a common file format used for documents. To extract text from them,
we'll use a Python library called pdfplumber. First, you'll need to import the
library, then open the PDF file using the open method, and finally extract the
text from each page. Here's how to do it: ...
```

The concise version assumes the model knows what PDFs are, understands Python imports, and can read code. All reasonable assumptions for a coding agent.

**When to elaborate:** domain-specific concepts, non-obvious patterns, subtle invariants, workarounds for specific bugs. Not for common programming knowledge, standard library usage, or well-known tools.

## Degrees of Freedom Principle

Match specificity to task fragility and variability.

**High freedom** — multiple valid approaches, creative tasks:

```markdown
## Instructions

1. Analyze code structure and organization
2. Check for potential bugs or edge cases
3. Suggest improvements for readability
4. Verify adherence to project conventions
```

**Low freedom** — fragile operations where deviation causes failures:

````markdown
## Instructions

Run exactly this script:

```bash
python scripts/migrate.py --verify --backup
```

Do not modify the command or add flags.
````

Mismatched specificity causes problems:
- Too much freedom on fragile tasks → errors and failures
- Too little freedom on creative tasks → rigid, suboptimal outputs

## Model Testing Principle

Skills act as additions to models. What works for a high-reasoning model might need more detail for a smaller model.

Test your skill with all models you plan to use:

- **Small/fast model** — Does the skill provide enough guidance? Are examples complete?
- **Balanced model** — Is the skill clear and efficient? Does progressive disclosure work?
- **High-reasoning model** — Does the skill avoid over-explaining? Can it infer obvious steps?

For Claude deployments these may be Haiku, Sonnet, and Opus. For other clients, use the models actually available and intended for the skill; do not hardcode a model choice into native skill metadata.

Aim for instructions that work well across all target models:

````markdown
## Quick Start

Use pdfplumber for text extraction:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```

For scanned PDFs requiring OCR, use pdf2image with pytesseract instead.
````

This supports different model capabilities: smaller models get a complete working example, balanced models get a clear default with an escape hatch, and stronger models get enough context without over-explanation.

## Progressive Disclosure Principle

`SKILL.md` serves as an overview. Reference files contain details. The agent loads reference files only when needed.

- Keep `SKILL.md` under 500 lines
- Split detailed content into reference files
- Keep references one level deep from `SKILL.md`
- Link to references from relevant sections with a clear description of what they contain

See [skill-structure.md](skill-structure.md) for progressive disclosure patterns.

## Validation Principle

Validation scripts are force multipliers. They catch errors the agent might miss and provide actionable feedback.

Good validation scripts:
- Provide verbose, specific error messages
- Show available valid options when something is invalid
- Pinpoint exact location of problems
- Suggest actionable fixes
- Are deterministic and reliable

See [workflows-and-validation.md](workflows-and-validation.md) for validation patterns.
