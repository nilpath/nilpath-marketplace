# Flowchart Template

A starter template for process flow diagrams.

## Template

```mermaid
flowchart TD
    %% Start node
    Start([Start]) --> Input[/Input Data/]

    %% Processing
    Input --> Process[Process Data]

    %% Decision point
    Process --> Check{Valid?}

    %% Branches
    Check -->|Yes| Success[Success Action]
    Check -->|No| Error[Error Handling]

    %% Convergence
    Success --> Output[/Output Result/]
    Error --> Retry{Retry?}
    Retry -->|Yes| Input
    Retry -->|No| Fail([Fail])

    %% End
    Output --> End([End])

    %% Styling
    classDef startEnd fill:#e1f5fe,stroke:#01579b
    classDef process fill:#fff3e0,stroke:#ff6f00
    classDef decision fill:#fce4ec,stroke:#c2185b
    classDef io fill:#e8f5e9,stroke:#2e7d32

    class Start,End,Fail startEnd
    class Process,Success,Error process
    class Check,Retry decision
    class Input,Output io
```

## Customization Points

1. **Direction**: Change `TD` to `LR` for left-to-right flow
2. **Nodes**: Replace placeholder text with your process steps
3. **Decisions**: Add or remove decision points as needed
4. **Styling**: Modify `classDef` colors to match your theme

## Node Shape Reference

| Shape | Syntax | Use For |
|-------|--------|---------|
| Rectangle | `[text]` | Actions, steps |
| Rounded | `(text)` | Start/End |
| Stadium | `([text])` | Terminals |
| Diamond | `{text}` | Decisions |
| Parallelogram | `[/text/]` | Input/Output |
| Database | `[(text)]` | Data storage |
