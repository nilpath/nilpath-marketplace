# Mindmap Syntax

Quick reference for Mermaid mindmaps.

## Basic Structure

```mermaid
mindmap
  root((Central Topic))
    Branch 1
      Leaf 1.1
      Leaf 1.2
    Branch 2
      Leaf 2.1
      Leaf 2.2
```

## Node Shapes

```mermaid
mindmap
  root((Circle))
    (Rounded)
    [Square]
    ))Cloud((
    )Hexagon(
```

## Icons

```mermaid
mindmap
  root((Project))
    ::icon(fa fa-book)
    Documentation
    ::icon(fa fa-code)
    Code
```

## Common Pattern: Project Planning

```mermaid
mindmap
  root((Project))
    Planning
      Requirements
      Timeline
      Resources
    Development
      Frontend
      Backend
      Database
    Testing
      Unit Tests
      Integration
      E2E
    Deployment
      Staging
      Production
```

## Common Pattern: Learning Topics

```mermaid
mindmap
  root((JavaScript))
    Fundamentals
      Variables
      Functions
      Objects
    DOM
      Selectors
      Events
      Manipulation
    Async
      Promises
      Async/Await
      Fetch API
    Frameworks
      React
      Vue
      Angular
```

## Full Documentation

[Mermaid Mindmap Docs](https://mermaid.js.org/syntax/mindmap.html)
