# Gantt Chart Syntax

Quick reference for Mermaid Gantt charts.

## Basic Structure

```mermaid
gantt
    title Project Schedule
    dateFormat YYYY-MM-DD

    section Phase 1
    Task 1           :a1, 2024-01-01, 30d
    Task 2           :a2, after a1, 20d

    section Phase 2
    Task 3           :b1, after a2, 15d
```

## Date Formats

```mermaid
gantt
    dateFormat YYYY-MM-DD
    dateFormat DD-MM-YYYY
    dateFormat MM-DD-YYYY
```

## Task Syntax

```mermaid
gantt
    %% Named task with ID
    Task name    :id1, 2024-01-01, 30d

    %% Task after another
    Task 2       :id2, after id1, 2w

    %% Active task
    Active task  :active, id3, 2024-02-01, 10d

    %% Done task
    Done task    :done, id4, 2024-01-15, 5d

    %% Critical task
    Critical     :crit, id5, 2024-03-01, 7d

    %% Milestone (0 duration)
    Milestone    :milestone, m1, 2024-03-08, 0d
```

## Duration Units

- `d` - Days
- `w` - Weeks
- `h` - Hours (for hour format)

## Sections

```mermaid
gantt
    section Design
    Wireframes    :des1, 2024-01-01, 1w
    Mockups       :des2, after des1, 1w

    section Development
    Frontend      :dev1, after des2, 2w
    Backend       :dev2, after des1, 3w

    section Testing
    QA            :test1, after dev1, 1w
```

## Common Pattern: Sprint Planning

```mermaid
gantt
    title Sprint 1
    dateFormat YYYY-MM-DD

    section Backend
    API Design       :done, api1, 2024-01-08, 2d
    Implementation   :active, api2, after api1, 5d
    Testing          :api3, after api2, 2d

    section Frontend
    UI Components    :ui1, 2024-01-10, 4d
    Integration      :ui2, after ui1, 3d

    section Release
    Code Review      :crit, cr1, after api3, 1d
    Deploy           :milestone, m1, after cr1, 0d
```

## Full Documentation

[Mermaid Gantt Chart Docs](https://mermaid.js.org/syntax/gantt.html)
