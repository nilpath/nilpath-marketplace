# Git Graph Syntax

Quick reference for Mermaid git graphs.

## Basic Structure

```mermaid
gitGraph
    commit
    commit
    branch develop
    checkout develop
    commit
    commit
    checkout main
    merge develop
    commit
```

## Commits

```mermaid
gitGraph
    commit id: "Initial"
    commit id: "Add feature"
    commit id: "Fix bug" type: REVERSE
    commit id: "v1.0" tag: "v1.0"
```

## Commit Types

- `NORMAL` - Regular commit (default)
- `REVERSE` - Reverted commit
- `HIGHLIGHT` - Highlighted commit

## Branches

```mermaid
gitGraph
    commit
    branch feature
    checkout feature
    commit
    commit
    checkout main
    merge feature
```

## Common Pattern: Git Flow

```mermaid
gitGraph
    commit id: "init"
    branch develop
    checkout develop
    commit id: "dev-1"

    branch feature/login
    checkout feature/login
    commit id: "login-1"
    commit id: "login-2"
    checkout develop
    merge feature/login

    branch feature/api
    checkout feature/api
    commit id: "api-1"
    checkout develop
    merge feature/api

    checkout main
    merge develop tag: "v1.0"
```

## Common Pattern: Hotfix

```mermaid
gitGraph
    commit id: "v1.0" tag: "v1.0"
    branch hotfix
    checkout hotfix
    commit id: "fix critical bug" type: REVERSE
    checkout main
    merge hotfix tag: "v1.0.1"
    branch develop
    checkout develop
    merge hotfix
```

## Full Documentation

[Mermaid Git Graph Docs](https://mermaid.js.org/syntax/gitgraph.html)
