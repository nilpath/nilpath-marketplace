# Architecture Diagram Template

A starter template for system architecture visualization.

## Template

```mermaid
flowchart TB
    %% External
    subgraph External[External Systems]
        User([User])
        ThirdParty[Third Party API]
    end

    %% Presentation Layer
    subgraph Presentation[Presentation Layer]
        Web[Web App]
        Mobile[Mobile App]
        Admin[Admin Panel]
    end

    %% API Layer
    subgraph API[API Layer]
        Gateway[API Gateway]
        Auth[Auth Service]
        BFF[BFF Service]
    end

    %% Business Layer
    subgraph Business[Business Layer]
        UserSvc[User Service]
        OrderSvc[Order Service]
        NotifySvc[Notification Service]
    end

    %% Data Layer
    subgraph Data[Data Layer]
        DB[(PostgreSQL)]
        Cache[(Redis)]
        Queue[(Message Queue)]
    end

    %% Connections
    User --> Web & Mobile
    Web & Mobile & Admin --> Gateway
    Gateway --> Auth
    Gateway --> BFF
    BFF --> UserSvc & OrderSvc
    UserSvc --> DB & Cache
    OrderSvc --> DB & Queue
    Queue --> NotifySvc
    NotifySvc --> ThirdParty

    %% Styling
    classDef external fill:#ffecb3,stroke:#ff8f00
    classDef presentation fill:#e3f2fd,stroke:#1565c0
    classDef api fill:#f3e5f5,stroke:#7b1fa2
    classDef business fill:#e8f5e9,stroke:#2e7d32
    classDef data fill:#fce4ec,stroke:#c2185b

    class User,ThirdParty external
    class Web,Mobile,Admin presentation
    class Gateway,Auth,BFF api
    class UserSvc,OrderSvc,NotifySvc business
    class DB,Cache,Queue data
```

## Customization Points

1. **Layers**: Add or remove architectural layers
2. **Services**: Replace with your actual services
3. **Data stores**: Update with your databases/caches
4. **Connections**: Map actual service dependencies
5. **Colors**: Match your organization's style guide

## Alternative: C4 Model Style

```mermaid
flowchart TB
    subgraph boundary[System Boundary]
        direction TB
        subgraph web[Web Application]
            SPA[Single Page App]
        end
        subgraph api[API Application]
            REST[REST API]
        end
        subgraph db[Database]
            PG[(PostgreSQL)]
        end
    end

    User([User]) --> SPA
    SPA --> REST
    REST --> PG
```

## Tips

- Group related components in subgraphs
- Use consistent colors per layer/type
- Show key data flows, not every connection
- Keep readable: max ~15-20 nodes
