# Agent Architecture

Quick reference for agent design. For detailed guidance, use: `/create-agent`

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

## Quick Reference

| Role | Tools | Use For |
|------|-------|---------|
| Reviewer | Read, Glob, Grep | Read-only analysis |
| Researcher | Read, Glob, Grep, WebFetch | Information gathering |
| Implementer | Read, Write, Edit, Bash | Code modification |

## See Also

- [Skill Architecture](skill-architecture.md)
- [Release Workflow](release-workflow.md)
- [Official Agent Docs](https://code.claude.com/docs/en/sub-agents)
