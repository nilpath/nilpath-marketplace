# Common Patterns

Reusable Mermaid diagram patterns and anti-patterns.

## Subgraphs for Grouping

```mermaid
flowchart TB
    subgraph Client[Client Layer]
        Web[Web App]
        Mobile[Mobile App]
    end
    subgraph Server[Server Layer]
        API[API Gateway]
        Auth[Auth Service]
    end
    subgraph Data[Data Layer]
        DB[(Database)]
        Cache[(Cache)]
    end

    Web --> API
    Mobile --> API
    API --> Auth
    API --> DB
    API --> Cache
```

## Direction Changes in Subgraphs

```mermaid
flowchart LR
    subgraph TOP
        direction TB
        A --> B
    end
    subgraph BOTTOM
        direction TB
        C --> D
    end
    TOP --> BOTTOM
```

## Multi-Diagram Documents

Use multiple fenced code blocks:

    ## System Overview

    ```mermaid
    flowchart LR
        A --> B --> C
    ```

    ## Sequence Flow

    ```mermaid
    sequenceDiagram
        A->>B: Request
        B-->>A: Response
    ```

## Click Events

```mermaid
flowchart LR
    A[Link] --> B[Callback]
    click A "https://example.com" _blank
    click B callback "Tooltip"
```

## Anti-Patterns

### Too Many Nodes

**Bad:**
```mermaid
flowchart LR
    A-->B-->C-->D-->E-->F-->G-->H-->I-->J
```

**Better:** Use subgraphs or split into multiple diagrams.

### Missing Labels

**Bad:**
```mermaid
flowchart LR
    A --> B
    B --> C
    B --> D
```

**Better:**
```mermaid
flowchart LR
    A -->|process| B
    B -->|success| C
    B -->|failure| D
```

### Inconsistent Arrows

**Bad:**
```mermaid
flowchart LR
    A --> B
    B -.-> C
    C ==> D
    D --- E
```

**Better:** Use consistent arrow style unless differences are meaningful.

### Wrong Diagram Type

| Information Type | Recommended Diagram |
|-----------------|---------------------|
| Process flow | Flowchart |
| API interactions | Sequence |
| Object relationships | Class |
| Database schema | ER |
| State transitions | State |
| Project timeline | Gantt |

## Accessibility Tips

- Use high contrast colors
- Add descriptive labels
- Keep diagrams focused
- Provide alt text in markdown
- Test with screen readers

## Performance Tips

- Limit nodes to ~50 per diagram
- Use subgraphs for large diagrams
- Split complex flows into multiple diagrams
- Avoid circular references when possible
