# Sequence Diagram Syntax

Quick reference for Mermaid sequence diagrams.

## Participants

```mermaid
sequenceDiagram
    participant A as Alice
    participant B as Bob
    actor U as User
```

## Message Types

```mermaid
sequenceDiagram
    A->>B: Solid arrow (sync)
    B-->>A: Dotted arrow (async/response)
    A-)B: Open arrow (async)
    B--)A: Open dotted arrow
    A-xB: Cross (lost message)
    B--xA: Dotted cross
```

## Activation

```mermaid
sequenceDiagram
    participant A
    participant B
    A->>+B: Request (activate B)
    B-->>-A: Response (deactivate B)
```

Or explicitly:

```mermaid
sequenceDiagram
    A->>B: Request
    activate B
    B-->>A: Response
    deactivate B
```

## Notes

```mermaid
sequenceDiagram
    A->>B: Message
    Note right of B: Note on right
    Note left of A: Note on left
    Note over A,B: Note spanning both
```

## Loops and Conditionals

```mermaid
sequenceDiagram
    loop Every minute
        A->>B: Heartbeat
    end

    alt Success
        B-->>A: OK
    else Failure
        B-->>A: Error
    end

    opt Optional step
        A->>B: Extra call
    end
```

## Parallel

```mermaid
sequenceDiagram
    par Action 1
        A->>B: Request 1
    and Action 2
        A->>C: Request 2
    end
```

## Common Pattern: API Call

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant D as Database

    C->>+S: POST /api/users
    S->>+D: INSERT user
    D-->>-S: user_id
    S-->>-C: 201 Created
```

## Full Documentation

[Mermaid Sequence Diagram Docs](https://mermaid.js.org/syntax/sequenceDiagram.html)
