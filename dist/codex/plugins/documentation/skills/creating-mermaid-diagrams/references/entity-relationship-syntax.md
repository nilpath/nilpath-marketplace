# Entity Relationship Diagram Syntax

Quick reference for Mermaid ER diagrams.

## Entity Definition

```mermaid
erDiagram
    CUSTOMER {
        int id PK
        string name
        string email UK
        date created_at
    }
```

## Attribute Types

- `PK` - Primary Key
- `FK` - Foreign Key
- `UK` - Unique Key

## Relationships

```mermaid
erDiagram
    A ||--o{ B : "one to many"
    C ||--|| D : "one to one"
    E }o--o{ F : "many to many"
```

## Cardinality Notation

| Symbol | Meaning |
|--------|---------|
| `\|\|` | Exactly one |
| `o\|` | Zero or one |
| `}o` | Zero or many |
| `}\|` | One or many |

## Relationship Labels

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "is in"
```

## Common Pattern: E-commerce

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : "ordered in"
    PRODUCT }|--|| CATEGORY : "belongs to"

    CUSTOMER {
        int id PK
        string name
        string email UK
    }
    ORDER {
        int id PK
        int customer_id FK
        date order_date
        string status
    }
    ORDER_ITEM {
        int id PK
        int order_id FK
        int product_id FK
        int quantity
    }
    PRODUCT {
        int id PK
        string name
        decimal price
        int category_id FK
    }
    CATEGORY {
        int id PK
        string name
    }
```

## Full Documentation

[Mermaid ER Diagram Docs](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)
