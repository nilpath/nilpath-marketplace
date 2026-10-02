# Skill Structure Reference

Skills have three structural components: YAML frontmatter (metadata), markdown body (content), and progressive disclosure (file organization).

## YAML Frontmatter

Every skill starts with YAML frontmatter between `---` markers. Our convention requires `name` and `description`.

```yaml
---
name: skill-name-here
description: What it does and when to use it (third person, specific triggers)
---
```

### Name field

Validation rules:
- Lowercase letters, numbers, hyphens only (max 64 characters)
- No reserved words: "anthropic", "claude"
- Must match directory name exactly
- Becomes the `/slash-command`

Examples:
- `process-pdfs` ✓
- `manage-facebook-ads` ✓
- `creating-agents` ✓
- `PDF_Processor` ✗ (uppercase)
- `helper` ✗ (vague)
- `claude-helper` ✗ (reserved word)

### Description field

Validation rules:
- Non-empty (our convention: required)
- Third person — never first or second person
- Include what it does AND when to use it
- Combined with `when_to_use`, truncated at 1,536 chars in the skill listing

Third person rule:
- `Processes Excel files and generates reports` ✓
- `I can help you process Excel files` ✗
- `You can use this to process Excel files` ✗

Effective description structure:

```yaml
description: Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

Avoid:
```yaml
description: Helps with documents
description: Processes data
```

### All frontmatter fields

See [official-spec.md](official-spec.md) for the full table of fields including `disable-model-invocation`, `arguments`, `context`, `agent`, and others.

## Markdown Body Structure

The body is standard markdown. Use headings to organize content — no XML tags.

```markdown
# Skill Name

## Quick Start
Fastest path to value — working example first.

## Instructions
Core step-by-step guidance Claude follows.

## Examples
Input/output pairs showing expected behavior.

## Advanced
Additional capabilities — link to reference files here.

## Guidelines
Rules and constraints.
```

The heading names are flexible — use what fits your skill. Common useful headings:

| Heading | Purpose |
|---------|---------|
| `## Quick Start` | Working example, fastest path |
| `## Instructions` | Core guidance |
| `## Examples` | Input/output pairs |
| `## Workflow` | Multi-step procedures |
| `## Advanced` | Deep-dive, links to references |
| `## Guidelines` | Rules and constraints |
| `## Troubleshooting` | Common failure modes |

## Naming Conventions

Use **verb-noun convention** for skill names:

| Pattern | Examples |
|---------|---------|
| `creating-*` | `creating-agents`, `creating-skills` |
| `manage-*` | `manage-facebook-ads`, `manage-zoom` |
| `setup-*` | `setup-stripe-payments` |
| `process-*` | `process-pdfs` |
| `generate-*` | `generate-ai-images` |

Avoid:
- Vague: `helper`, `utils`, `tools`
- Generic: `documents`, `data`, `files`
- Reserved words: `anthropic-helper`, `claude-tools`
- Mismatch: directory `facebook-ads` but name `facebook-ads-manager`

## Progressive Disclosure

Keep `SKILL.md` under 500 lines. Move detailed content to separate files.

### High-level guide pattern

Quick start in `SKILL.md`, details in reference files:

```markdown
---
name: pdf-processing
description: Extracts text and tables from PDF files, fills forms, merges documents.
---

# PDF Processing

## Quick Start

Extract text with pdfplumber:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```

## Advanced

**Form filling**: See [forms.md](forms.md)
**API reference**: See [reference.md](reference.md)
```

Claude reads `forms.md` or `reference.md` only when needed.

### Domain organization pattern

For skills with multiple domains, organize by domain:

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── references/
    ├── finance.md (revenue, billing)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

When the user asks about revenue, Claude reads only `finance.md`.

### Critical rules

- **One level deep**: all reference files link directly from `SKILL.md`. Avoid `SKILL.md → advanced.md → details.md` — Claude may only partially read deeply nested files.
- **Table of contents**: for reference files over 100 lines, include a ToC at the top.
- **Forward slashes**: always use `scripts/helper.py` not `scripts\helper.py`.

## File Organization

```
skill-name/
├── SKILL.md              # Required — entry point
├── references/           # Domain knowledge, loaded on demand
│   ├── guide-1.md
│   └── examples.md
├── templates/            # Output structures for Claude to fill in
│   └── report.md
├── workflows/            # Step-by-step procedures
│   └── create.md
└── scripts/              # Utility scripts (executed, not loaded)
    └── validate.sh
```

Files in `scripts/` are executed by Claude — they are not loaded into context as text. Name them descriptively: `form_validation_rules.md` not `doc2.md`. Use forward slashes for paths.

## Validation Checklist

Before finalizing a skill:

- [ ] YAML frontmatter valid (`name` matches directory, `description` in third person)
- [ ] `name` and `description` present (our required convention)
- [ ] Body uses markdown headings — no XML tags
- [ ] `disable-model-invocation: true` set if skill has side effects
- [ ] Progressive disclosure applied (`SKILL.md` < 500 lines)
- [ ] Reference files linked from `SKILL.md` with descriptions
- [ ] All references one level deep
- [ ] File paths use forward slashes
- [ ] Descriptive file names
- [ ] All referenced files exist
