# Flowchart Syntax

Quick reference for Mermaid flowcharts.

## Direction

```mermaid
flowchart TD    %% Top to Down
flowchart LR    %% Left to Right
flowchart BT    %% Bottom to Top
flowchart RL    %% Right to Left
```

## Node Shapes

```mermaid
flowchart LR
    A[Rectangle]
    B(Rounded)
    C([Stadium])
    D[[Subroutine]]
    E[(Database)]
    F((Circle))
    G>Asymmetric]
    H{Diamond}
    I{{Hexagon}}
    J[/Parallelogram/]
    K[\Parallelogram alt\]
    L[/Trapezoid\]
    M[\Trapezoid alt/]
```

## Arrow Types

```mermaid
flowchart LR
    A --> B       %% Arrow
    C --- D       %% Line
    E -.-> F      %% Dotted arrow
    G ==> H       %% Thick arrow
    I --text--> J %% Arrow with text
    K -->|text| L %% Arrow with text (alt)
```

## Subgraphs

```mermaid
flowchart TB
    subgraph Group1[First Group]
        A --> B
    end
    subgraph Group2[Second Group]
        C --> D
    end
    B --> C
```

## Styling

```mermaid
flowchart LR
    A:::highlight --> B
    classDef highlight fill:#f96,stroke:#333
```

## Common Patterns

### Decision Flow

```mermaid
flowchart TD
    Start --> Check{Condition?}
    Check -->|Yes| Action1
    Check -->|No| Action2
    Action1 --> End
    Action2 --> End
```

### Process with Validation

```mermaid
flowchart LR
    Input --> Validate{Valid?}
    Validate -->|Yes| Process --> Output
    Validate -->|No| Error --> Input
```

## Full Documentation

[Mermaid Flowchart Docs](https://mermaid.js.org/syntax/flowchart.html)
