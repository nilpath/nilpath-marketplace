# Skill Architecture

Quick reference for skill structure. For detailed guidance, use: `/create-skill`

## Directory Structure

```mermaid
flowchart TD
    SKILL[SKILL.md<br/>Entry Point] --> REF[references/]
    SKILL --> TEMP[templates/]
    SKILL --> WORK[workflows/]
    SKILL --> SCRIPT[scripts/]

    REF --> R1[syntax-guide.md]
    REF --> R2[common-patterns.md]

    TEMP --> T1[starter.md]
    TEMP --> T2[advanced.md]

    WORK --> W1[create.md]
    WORK --> W2[edit.md]

    SCRIPT --> S1[validate.sh]
    SCRIPT --> S2[automate.sh]
```

## Progressive Disclosure Pattern

```mermaid
flowchart LR
    subgraph "Always Loaded"
        SKILL[SKILL.md<br/>~300 lines]
    end

    subgraph "Loaded On Demand"
        REF1[reference-1.md<br/>~50 lines]
        REF2[reference-2.md<br/>~50 lines]
        WORK[workflow.md<br/>~100 lines]
    end

    SKILL -->|"See [reference]()"| REF1
    SKILL -->|"See [reference]()"| REF2
    SKILL -->|"Follow [workflow]()"| WORK
```

## Quick Reference

| Component | Purpose | Line Limit |
|-----------|---------|------------|
| SKILL.md | Entry point with quick start | ~500 |
| references/ | Syntax guides, patterns | ~50 each |
| templates/ | Copy-paste starters | varies |
| workflows/ | Step-by-step guides | ~100 each |
| scripts/ | Automation (executed, not loaded) | ~200 each |

## Naming Conventions

| Type | Pattern | Examples |
|------|---------|----------|
| Skill name | `creating-*`, `managing-*` | `creating-agents`, `git-commits` |
| References | `*-syntax.md`, `*-patterns.md` | `common-patterns.md` |
| Workflows | `create-*.md`, `edit-*.md` | `create-new.md` |
| Scripts | `validate-*.sh` | `validate-diagram.sh` |

## See Also

- [Agent Architecture](agent-architecture.md)
- [Release Workflow](release-workflow.md)
- [Official Skills Docs](https://code.claude.com/docs/en/skills)
