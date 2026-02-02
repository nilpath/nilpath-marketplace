# Sequence Diagram Template

A starter template for API/service interaction diagrams.

## Template

```mermaid
sequenceDiagram
    autonumber

    %% Participants
    participant C as Client
    participant G as API Gateway
    participant A as Auth Service
    participant S as Service
    participant D as Database

    %% Authentication flow
    C->>+G: Request with token
    G->>+A: Validate token
    A-->>-G: Token valid

    %% Main request flow
    G->>+S: Forward request
    S->>+D: Query data
    D-->>-S: Results

    %% Response
    S-->>-G: Response data
    G-->>-C: JSON response

    %% Notes
    Note over G,A: Authentication happens first
    Note over S,D: Business logic here
```

## Customization Points

1. **Participants**: Replace with your system components
2. **Messages**: Update with your API calls
3. **Activation**: Use `+`/`-` to show processing time
4. **Notes**: Add context where helpful

## Message Types

| Arrow | Meaning |
|-------|---------|
| `->>` | Synchronous request |
| `-->>` | Response/async |
| `-)` | Async message |
| `-x` | Lost message |

## Adding Error Handling

```mermaid
sequenceDiagram
    C->>S: Request
    alt Success
        S-->>C: 200 OK
    else Validation Error
        S-->>C: 400 Bad Request
    else Server Error
        S-->>C: 500 Error
    end
```

## Adding Loops

```mermaid
sequenceDiagram
    loop Retry 3 times
        C->>S: Request
        S-->>C: Response
    end
```
