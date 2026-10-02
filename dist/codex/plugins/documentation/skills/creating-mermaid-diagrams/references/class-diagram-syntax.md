# Class Diagram Syntax

Quick reference for Mermaid class diagrams.

## Class Definition

```mermaid
classDiagram
    class Animal {
        +String name
        -int age
        #String species
        ~void internalMethod()
        +makeSound() String
        +move(int distance) void
    }
```

## Visibility Markers

- `+` Public
- `-` Private
- `#` Protected
- `~` Package/Internal

## Relationships

```mermaid
classDiagram
    A <|-- B : Inheritance
    C *-- D : Composition
    E o-- F : Aggregation
    G --> H : Association
    I -- J : Link
    K ..> L : Dependency
    M ..|> N : Realization
```

## Cardinality

```mermaid
classDiagram
    Customer "1" --> "*" Order : places
    Order "1" *-- "1..*" LineItem : contains
```

- `1` - Exactly one
- `0..1` - Zero or one
- `*` - Many
- `1..*` - One or more
- `n..m` - Range

## Annotations

```mermaid
classDiagram
    class Shape {
        <<abstract>>
        +draw()
    }
    class Serializable {
        <<interface>>
        +serialize()
    }
    class Color {
        <<enumeration>>
        RED
        GREEN
        BLUE
    }
```

## Common Pattern: Repository

```mermaid
classDiagram
    class Repository~T~ {
        <<interface>>
        +findById(id) T
        +save(entity) T
        +delete(id) void
    }
    class UserRepository {
        +findByEmail(email) User
    }
    Repository~User~ <|.. UserRepository
```

## Full Documentation

[Mermaid Class Diagram Docs](https://mermaid.js.org/syntax/classDiagram.html)
