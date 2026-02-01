# Agent Architecture

Deep dive into Claude Code agent design and delegation patterns.

## Agent Delegation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Claude
    participant A as Agent
    participant T as Tools

    U->>C: Request task
    C->>C: Match description keywords
    C->>A: Delegate with context
    A->>T: Execute tools
    T-->>A: Results
    A-->>C: Completion report
    C-->>U: Summary
```

## Agent Definition Format

Agents are defined in markdown files with YAML frontmatter:

```yaml
---
name: agent-name
description: Expert at X. Use when Y or Z.
tools: Read, Glob, Grep
skills:
  - required-skill
model: sonnet
---

# Agent Name

System prompt instructions here...
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `description` | Yes | Capabilities + trigger keywords |
| `tools` | Yes | Available tools |
| `skills` | No | Preloaded skills |
| `model` | No | haiku, sonnet, opus |

## Directory Organization

Agents are grouped by category:

```
agents/
├── review/           # Code review agents
│   └── code-reviewer.md
├── research/         # Research and exploration
│   └── codebase-explorer.md
└── implementation/   # Code writing agents
    └── feature-builder.md
```

## Tool Permissions by Role

| Role | Tools | Rationale |
|------|-------|-----------|
| **Reviewer** | Read, Glob, Grep | Read-only analysis |
| **Researcher** | Read, Glob, Grep, WebFetch | Information gathering |
| **Implementer** | Read, Write, Edit, Bash | Code modification |

## Model Selection Guide

```mermaid
flowchart TD
    START{Task Type?} -->|Fast, simple| HAIKU[haiku]
    START -->|Balanced| SONNET[sonnet]
    START -->|Complex reasoning| OPUS[opus]

    HAIKU --> H1[Formatting]
    HAIKU --> H2[Simple search]
    HAIKU --> H3[Quick checks]

    SONNET --> S1[Code review]
    SONNET --> S2[Bug fixes]
    SONNET --> S3[Standard features]

    OPUS --> O1[Architecture design]
    OPUS --> O2[Complex refactoring]
    OPUS --> O3[Security analysis]
```

## Orchestration Patterns

### Fan-Out (Parallel)

```mermaid
flowchart TD
    MAIN[Main Agent] --> A1[Agent 1]
    MAIN --> A2[Agent 2]
    MAIN --> A3[Agent 3]
    A1 --> MERGE[Merge Results]
    A2 --> MERGE
    A3 --> MERGE
```

Use when tasks are independent and can run simultaneously.

### Pipeline (Sequential)

```mermaid
flowchart LR
    A[Research] --> B[Plan] --> C[Implement] --> D[Review]
```

Use when each step depends on the previous result.

### Orchestrator-Worker

```mermaid
flowchart TD
    ORCH[Orchestrator] --> W1[Worker 1]
    ORCH --> W2[Worker 2]
    W1 -->|Result| ORCH
    W2 -->|Result| ORCH
    ORCH --> W3[Worker 3]
    W3 -->|Result| ORCH
```

Use for dynamic task distribution with coordination.

## Description Keywords

Include trigger words in agent descriptions for proper delegation:

| Domain | Keywords |
|--------|----------|
| Review | review, audit, check, analyze, quality |
| Security | security, vulnerability, OWASP, CVE |
| Performance | performance, optimize, profile, benchmark |
| Testing | test, coverage, unit, integration |
| Documentation | docs, readme, comments, jsdoc |

## Skills Dependencies

Agents can preload skills for specialized knowledge:

```yaml
skills:
  - gh-pr-review      # GitHub PR operations
  - git-stacked-prs   # Stacked PR workflow
```

Skills are loaded before the agent starts working.

## See Also

- [Skill Architecture](skill-architecture.md)
- [Release Workflow](release-workflow.md)
- [Official Agent Docs](https://code.claude.com/docs/en/sub-agents)
