# Class Diagram Template

A starter template for OOP and type relationship diagrams.

## Template

```mermaid
classDiagram
    %% Interface
    class IRepository~T~ {
        <<interface>>
        +findById(id: string) T
        +findAll() List~T~
        +save(entity: T) T
        +delete(id: string) void
    }

    %% Abstract base class
    class BaseEntity {
        <<abstract>>
        +string id
        +DateTime createdAt
        +DateTime updatedAt
        #validate() bool
    }

    %% Concrete classes
    class User {
        +string email
        +string name
        -string passwordHash
        +authenticate(password) bool
        +updateProfile(data) void
    }

    class UserRepository {
        -Database db
        +findByEmail(email) User
        +findById(id) User
        +save(user) User
    }

    %% Relationships
    BaseEntity <|-- User : extends
    IRepository~User~ <|.. UserRepository : implements
    UserRepository --> User : manages
```

## Customization Points

1. **Classes**: Replace with your domain entities
2. **Methods**: Add your business logic methods
3. **Relationships**: Update inheritance and associations
4. **Annotations**: Use `<<interface>>`, `<<abstract>>`, `<<enumeration>>`

## Visibility Markers

| Symbol | Access Level |
|--------|--------------|
| `+` | Public |
| `-` | Private |
| `#` | Protected |
| `~` | Package |

## Relationship Types

| Arrow | Meaning |
|-------|---------|
| `<\|--` | Inheritance |
| `<\|..` | Implementation |
| `*--` | Composition |
| `o--` | Aggregation |
| `-->` | Association |
| `..>` | Dependency |

## Adding Cardinality

```mermaid
classDiagram
    Customer "1" --> "*" Order : places
    Order "1" *-- "1..*" OrderItem : contains
```
