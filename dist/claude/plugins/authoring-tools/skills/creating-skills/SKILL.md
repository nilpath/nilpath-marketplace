---
name: creating-skills
description: Expert guidance for creating, writing, and refining agent skills. Invoke explicitly to author new skills, improve existing skills, or understand skill structure and best practices.
argument-hint: '[skill description or requirements]'
disable-model-invocation: true
---

# Creating Agent Skills

This skill teaches how to create effective skills for the active client, following its native specification.


Invoke explicitly with `/authoring-tools:creating-skills`. Do not load this skill automatically.


## Authoring Target and Placement

**Default: native skills for the active client.** Write an ordinary `SKILL.md`, not a marketplace template. Read [authoring-targets.md](references/authoring-targets.md) before creating or editing files.

- Ask whether placement is **workspace** or **personal** when unspecified, using the `AskUserQuestion` tool.
- Follow an existing project discovery convention; choose one location, not duplicate copies.
- Resolve the selected skill directory before touching resources. Confirm before overwriting existing files.
- Choose output invocation policy independently: created skills may be automatically discoverable or explicit-only. This authoring skill's manual-only policy is not a default for every output.
- Use marketplace-source authoring only when explicitly requested. Source-only `targets`, canonical tools, and Jinja do not belong in native `SKILL.md` files.

## Core Principles

### 1. Skills Are Prompts

All prompting best practices apply. Be clear, be direct. Assume the agent is capable - only add context it doesn't have.

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

Native examples in this guide use required `name` and `description`: an unprefixed name matching its folder (at most 64 lowercase letters, numbers, and hyphens), and a non-empty description of at most 1,024 characters. Include triggers in the description.


Claude permits defaults for these fields; this authoring convention is intentionally stricter.

| Field | Convention | Description |
|-------|------------|-------------|
| `name` | Required | Lowercase letters, numbers, hyphens only (max 64 chars). Becomes the `/slash-command`. Defaults to directory name if omitted. |
| `description` | Required | What it does AND when to use it (third person; at most 1,024 characters). |
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

Avoid vague names such as `helper`, `utils`, and `tools`. Do not put a plugin prefix or invocation sigil in the `name` field.

Also avoid reserved names such as `anthropic-*` and `claude-*`.


### Body Structure

Use standard markdown headings:

```markdown
# Skill Name

## Quick Start
Fastest path to value...

## Instructions
Core guidance the agent follows...

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
5. **Verify accuracy** - Check technical claims against current sources
6. **Upgrade structure** - Refactor an existing skill into a router
7. **Create domain expertise** - Build comprehensive lifecycle guidance

Use a clear request to select the workflow directly; ask only when intent is ambiguous.

| Intent | Workflow |
|--------|----------|
| Create | [create-new-skill.md](workflows/create-new-skill.md) |
| Audit | [audit-skill.md](workflows/audit-skill.md) |
| Add workflow | [add-workflow.md](workflows/add-workflow.md) |
| Add reference | [add-reference.md](workflows/add-reference.md) |
| Add script | [add-script.md](workflows/add-script.md) |
| Add template | [add-template.md](workflows/add-template.md) |
| Guidance | [get-guidance.md](workflows/get-guidance.md) |
| Verify | [verify-skill.md](workflows/verify-skill.md) |
| Upgrade | [upgrade-to-router.md](workflows/upgrade-to-router.md) |
| Domain expertise | [create-domain-expertise-skill.md](workflows/create-domain-expertise-skill.md) |

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

Resolve placement and invocation mode first via the create workflow. The following is a **native, automatically discoverable** example; explicit-only alternatives are in [invocation-and-arguments.md](references/invocation-and-arguments.md).

````markdown
---
name: your-skill-name
description: "[What it does]. Use when [trigger conditions]."
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
````

### Step 3: Add Reference Files (If Needed)

Link from SKILL.md to detailed content:

```markdown
For API reference, see [REFERENCE.md](REFERENCE.md).
For form filling guide, see [FORMS.md](FORMS.md).
```

Keep references **one level deep** from SKILL.md.

### Step 4: Add Scripts (If Needed)

Resolve scripts relative to the selected skill's directory, not the process working directory. Assign `SKILL_DIR` explicitly from the discovered `SKILL.md` location; it is an ordinary shell variable, not a client-provided substitution. Scripts execute through the client's shell tool and normal approval rules:

````markdown
## Utility Scripts

Extract fields:
```bash
python "$SKILL_DIR/scripts/analyze.py" input.pdf > fields.json
```
````

### Step 5: Test With Real Usage

1. Test with actual tasks, not test scenarios
2. Observe where the agent struggles
3. Refine based on real behavior
4. Test with the models and client versions intended for actual use

## Auditing Existing Skills

Check against this rubric:

- [ ] Valid YAML frontmatter (`name` + `description` present — our required convention)
- [ ] Description includes trigger keywords (third person, specific)
- [ ] Uses standard markdown headings (not XML tags)
- [ ] Invocation policy matches user intent and uses the active client's supported mechanism
- [ ] SKILL.md under 500 lines
- [ ] References one level deep
- [ ] Examples are concrete, not abstract
- [ ] Consistent terminology
- [ ] No time-sensitive information
- [ ] Scripts handle errors explicitly
- [ ] One discovery location selected; no duplicate skill or unnecessary command/prompt file created

## Common Patterns

### Template Pattern

Provide output templates for consistent results:

````markdown
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
````

### Workflow Pattern

For complex multi-step tasks:

````markdown
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
````

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
- **Punting to the agent** - Scripts should handle errors
- **Time-sensitive info** - Use "old patterns" section instead

## Reference Files

For detailed guidance, see:

- [authoring-targets.md](references/authoring-targets.md) - Native placement, safe edits, and opt-in marketplace sources
- [official-spec.md](references/official-spec.md) - Active-client locations, supported metadata, and execution rules
- [invocation-and-arguments.md](references/invocation-and-arguments.md) - Automatic versus explicit-only skills, inputs, and resource execution
- [best-practices.md](references/best-practices.md) - Skill authoring best practices
- [skill-structure.md](references/skill-structure.md) - Metadata, naming, and progressive disclosure
- [recommended-structure.md](references/recommended-structure.md) - Router and workflow templates
- [core-principles.md](references/core-principles.md) - Conciseness, freedom, and validation
- [common-patterns.md](references/common-patterns.md) - Examples, templates, and invocation patterns
- [be-clear-and-direct.md](references/be-clear-and-direct.md) - Precise instructions and edge cases
- [workflows-and-validation.md](references/workflows-and-validation.md) - Checklists, feedback loops, and recovery
- [iteration-and-testing.md](references/iteration-and-testing.md) - Evaluation and discovery testing
- [using-scripts.md](references/using-scripts.md) - Reusable executable resources
- [executable-code.md](references/executable-code.md) - Dependencies and script execution
- [using-templates.md](references/using-templates.md) - Reusable output structures
- [api-security.md](references/api-security.md) - Credentials and API wrappers

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
