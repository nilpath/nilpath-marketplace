# Styling and Themes

Quick reference for Mermaid styling options.

## Built-in Themes

```mermaid
%%{init: {'theme': 'default'}}%%
flowchart LR
    A --> B
```

Available themes:
- `default` - Light theme
- `dark` - Dark theme
- `forest` - Green tones
- `neutral` - Grayscale
- `base` - Minimal styling

## Theme Configuration

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#BB2528',
    'primaryTextColor': '#fff',
    'primaryBorderColor': '#7C0000',
    'lineColor': '#F8B229',
    'secondaryColor': '#006100'
  }
}}%%
flowchart LR
    A --> B --> C
```

## Node Styling with classDef

```mermaid
flowchart LR
    A:::success --> B:::warning --> C:::error

    classDef success fill:#90EE90,stroke:#228B22
    classDef warning fill:#FFD700,stroke:#FFA500
    classDef error fill:#FF6B6B,stroke:#DC143C
```

## Apply Style to Multiple Nodes

```mermaid
flowchart LR
    A --> B --> C
    D --> E --> F

    class A,D success
    class B,E warning
    class C,F error

    classDef success fill:#90EE90
    classDef warning fill:#FFD700
    classDef error fill:#FF6B6B
```

## Link Styling

```mermaid
flowchart LR
    A --> B --> C

    linkStyle 0 stroke:#ff3,stroke-width:4px
    linkStyle 1 stroke:#0f0,stroke-width:2px,stroke-dasharray:5
```

## Subgraph Styling

```mermaid
flowchart TB
    subgraph Backend[Backend Services]
        style Backend fill:#e1f5fe
        API --> DB
    end
    subgraph Frontend[Frontend]
        style Frontend fill:#fff3e0
        UI --> API
    end
```

## Common Theme Variables

| Variable | Description |
|----------|-------------|
| `primaryColor` | Main node fill |
| `primaryTextColor` | Text on primary |
| `primaryBorderColor` | Node borders |
| `lineColor` | Arrow/line color |
| `secondaryColor` | Secondary nodes |
| `tertiaryColor` | Subgraph fills |
| `background` | Diagram background |

## Full Documentation

[Mermaid Theming Docs](https://mermaid.js.org/config/theming.html)
