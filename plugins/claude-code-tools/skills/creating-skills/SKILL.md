---
name: creating-skills
description: Expert guidance for creating, writing, and refining Claude Code Skills. Use when working with SKILL.md files, authoring new skills, improving existing skills, or understanding skill structure and best practices.
argument-hint: "[skill description or requirements]"
---

# Creating Agent Skills

This skill teaches how to create effective Claude Code Skills following Anthropic's official specification.

## Core Principles

### 1. Skills Are Prompts

All prompting best practices apply. Be clear, be direct. Assume Claude is smart - only add context Claude doesn't have.

### 2. Standard Markdown Format

Use YAML frontmatter + markdown body. **No XML tags** - use standard markdown headings.

```markdown
---
name: my-skill-name
description: What it does and when to use it
---

# My Skill Name

## Quick Start
Immediate actionable guidance...

## Instructions
Step-by-step procedures...

## Examples
Concrete usage examples...
```

### 3. Progressive Disclosure

Keep SKILL.md under 500 lines. Split detailed content into reference files. Load only what's needed.

```
my-skill/
├── SKILL.md              # Entry point (required)
├── reference.md          # Detailed docs (loaded when needed)
├── examples.md           # Usage examples
└── scripts/              # Utility scripts (executed, not loaded)
```

### 4. Effective Descriptions

The description field enables skill discovery. Include both what the skill does AND when to use it. Write in third person.

**Good:**
```yaml
description: Extracts text and tables from PDF files, fills forms, merges documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

**Bad:**
```yaml
description: Helps with documents
```

## Skill Structure

### Frontmatter Fields

Our convention treats `name` and `description` as **required** for discoverability, even though the official spec marks them as optional.

| Field | Convention | Description |
|-------|------------|-------------|
| `name` | Required | Lowercase letters, numbers, hyphens only (max 64 chars). Becomes the `/slash-command`. Defaults to directory name if omitted. |
| `description` | Required | What it does AND when to use it (third person). Combined with `when_to_use`, truncated at 1,536 chars in the listing. |
| `when_to_use` | No | Extra trigger phrases appended to `description` in the skill listing. |
| `argument-hint` | No | Hint shown during autocomplete, e.g. `[issue-number]` or `[filename] [format]`. |
| `arguments` | No | Named positional args for `$name` substitution. Space-separated string or YAML list. |
| `disable-model-invocation` | No | `true` prevents Claude from auto-loading. Use for side-effect workflows (`/commit`, `/deploy`). |
| `user-invocable` | No | `false` hides from the `/` menu. Use for background knowledge. |
| `allowed-tools` | No | Tools Claude can use without prompting, e.g. `Bash(git add *) Bash(git commit *)`. |
| `model` | No | Override model for this skill's turn. |
| `effort` | No | Override effort level: `low`, `medium`, `high`, `xhigh`, `max`. |
| `context` | No | `fork` runs the skill in an isolated subagent. |
| `agent` | No | Subagent type when `context: fork`. Built-ins: `Explore`, `Plan`, `general-purpose`. |
| `paths` | No | Glob patterns limiting when the skill auto-activates. |
| `hooks` | No | Hooks scoped to this skill's lifecycle. |
| `shell` | No | Shell for `` ! `command` `` injection blocks: `bash` (default) or `powershell`. |

### Naming Conventions

Use **gerund form** (verb + -ing) for skill names:

- `processing-pdfs`
- `analyzing-spreadsheets`
- `generating-commit-messages`
- `reviewing-code`

Avoid: `helper`, `utils`, `tools`, `anthropic-*`, `claude-*`

### Body Structure

Use standard markdown headings:

```markdown
# Skill Name

## Quick Start
Fastest path to value...

## Instructions
Core guidance Claude follows...

## Examples
Input/output pairs showing expected behavior...

## Advanced Features
Additional capabilities (link to reference files)...

## Guidelines
Rules and constraints...
```

## Commands → Skills Merge

Commands and skills are now equivalent — both create a `/slash-command`. A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both produce `/deploy` and work the same way. Existing `.claude/commands/` files keep working. Skills are preferred because they support supporting files, invocation control frontmatter, and automatic discovery.

The skill `name` field IS the slash command. No separate command file is needed.

## What Would You Like To Do?

1. **Create new skill** - Build from scratch
2. **Audit existing skill** - Check against best practices
3. **Add component** - Add workflow/reference/example
4. **Get guidance** - Understand skill design

## Creating a New Skill

### Step 1: Choose Type

**Simple skill (single file):**
- Under 500 lines
- Self-contained guidance
- No complex workflows

**Progressive disclosure skill (multiple files):**
- SKILL.md as overview
- Reference files for detailed docs
- Scripts for utilities

### Step 2: Create SKILL.md

```markdown
---
name: your-skill-name
description: [What it does]. Use when [trigger conditions].
---

# Your Skill Name

## Quick Start

[Immediate actionable example]

```[language]
[Code example]
```

## Instructions

[Core guidance]

## Examples

**Example 1:**
Input: [description]
Output:
```
[result]
```

## Guidelines

- [Constraint 1]
- [Constraint 2]
```

### Step 3: Add Reference Files (If Needed)

Link from SKILL.md to detailed content:

```markdown
For API reference, see [REFERENCE.md](REFERENCE.md).
For form filling guide, see [FORMS.md](FORMS.md).
```

Keep references **one level deep** from SKILL.md.

### Step 4: Add Scripts (If Needed)

Scripts execute without loading into context:

```markdown
## Utility Scripts

Extract fields:
```bash
python scripts/analyze.py input.pdf > fields.json
```
```

### Step 5: Test With Real Usage

1. Test with actual tasks, not test scenarios
2. Observe where Claude struggles
3. Refine based on real behavior
4. Test with Haiku, Sonnet, and Opus

## Auditing Existing Skills

Check against this rubric:

- [ ] Valid YAML frontmatter (`name` + `description` present — our required convention)
- [ ] Description includes trigger keywords (third person, specific)
- [ ] Uses standard markdown headings (not XML tags)
- [ ] `disable-model-invocation: true` set for side-effect workflows (deploy, commit, send)
- [ ] SKILL.md under 500 lines
- [ ] References one level deep
- [ ] Examples are concrete, not abstract
- [ ] Consistent terminology
- [ ] No time-sensitive information
- [ ] Scripts handle errors explicitly
- [ ] No separate `.claude/commands/` file created (skill name is the slash command)

## Common Patterns

### Template Pattern

Provide output templates for consistent results:

```markdown
## Report Template

```markdown
# [Analysis Title]

## Executive Summary
[One paragraph overview]

## Key Findings
- Finding 1
- Finding 2

## Recommendations
1. [Action item]
2. [Action item]
```
```

### Workflow Pattern

For complex multi-step tasks:

```markdown
## Migration Workflow

Copy this checklist:

```
- [ ] Step 1: Backup database
- [ ] Step 2: Run migration script
- [ ] Step 3: Validate output
- [ ] Step 4: Update configuration
```

**Step 1: Backup database**
Run: `./scripts/backup.sh`
...
```

### Conditional Pattern

Guide through decision points:

```markdown
## Choose Your Approach

**Creating new content?** Follow "Creation workflow" below.
**Editing existing?** Follow "Editing workflow" below.
```

## Anti-Patterns to Avoid

- **XML tags in body** - Use markdown headings instead
- **Vague descriptions** - Be specific with trigger keywords
- **Deep nesting** - Keep references one level from SKILL.md
- **Too many options** - Provide a default with escape hatch
- **Windows paths** - Always use forward slashes
- **Punting to Claude** - Scripts should handle errors
- **Time-sensitive info** - Use "old patterns" section instead

## Reference Files

For detailed guidance, see:

- [official-spec.md](references/official-spec.md) - Full frontmatter reference, string substitutions, shell injection, forked context
- [invocation-and-arguments.md](references/invocation-and-arguments.md) - Invocation control, arguments, shell injection, `context: fork`
- [best-practices.md](references/best-practices.md) - Skill authoring best practices

## Success Criteria

A well-structured skill:
- Has valid YAML frontmatter with descriptive name and description
- Uses standard markdown headings (not XML tags)
- Keeps SKILL.md under 500 lines
- Links to reference files for detailed content
- Includes concrete examples with input/output pairs
- Has been tested with real usage

Sources:
- [Agent Skills - Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [GitHub - anthropics/skills](https://github.com/anthropics/skills)
