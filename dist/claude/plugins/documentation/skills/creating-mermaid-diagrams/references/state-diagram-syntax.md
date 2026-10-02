# State Diagram Syntax

Quick reference for Mermaid state diagrams.

## Basic States

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing : start
    Processing --> Complete : done
    Complete --> [*]
```

## Transitions

```mermaid
stateDiagram-v2
    s1 --> s2 : event
    s2 --> s3 : event / action
```

## Composite States

```mermaid
stateDiagram-v2
    [*] --> Active
    state Active {
        [*] --> Running
        Running --> Paused : pause
        Paused --> Running : resume
    }
    Active --> [*] : stop
```

## Fork and Join

```mermaid
stateDiagram-v2
    state fork_state <<fork>>
    state join_state <<join>>

    [*] --> fork_state
    fork_state --> State1
    fork_state --> State2
    State1 --> join_state
    State2 --> join_state
    join_state --> [*]
```

## Choice

```mermaid
stateDiagram-v2
    state check <<choice>>
    [*] --> check
    check --> Valid : if valid
    check --> Invalid : if invalid
```

## Notes

```mermaid
stateDiagram-v2
    State1 : Description here
    State1 --> State2
    note right of State1 : Additional info
```

## Common Pattern: Order Status

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Processing : payment_received
    Processing --> Shipped : dispatched
    Shipped --> Delivered : delivered
    Delivered --> [*]

    Processing --> Cancelled : cancel
    Pending --> Cancelled : cancel
    Cancelled --> [*]
```

## Full Documentation

[Mermaid State Diagram Docs](https://mermaid.js.org/syntax/stateDiagram.html)
