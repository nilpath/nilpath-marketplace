# Pie Chart Syntax

Quick reference for Mermaid pie charts.

## Basic Structure

```mermaid
pie
    title Distribution
    "Category A" : 40
    "Category B" : 30
    "Category C" : 20
    "Category D" : 10
```

## With Title

```mermaid
pie showData
    title Browser Market Share
    "Chrome" : 65
    "Safari" : 19
    "Firefox" : 4
    "Edge" : 4
    "Other" : 8
```

## Options

- `showData` - Display percentages on the chart

## Common Pattern: Budget

```mermaid
pie showData
    title Monthly Budget
    "Housing" : 35
    "Food" : 15
    "Transportation" : 10
    "Utilities" : 10
    "Entertainment" : 10
    "Savings" : 20
```

## Common Pattern: Time Allocation

```mermaid
pie showData
    title Sprint Time Allocation
    "Development" : 50
    "Testing" : 20
    "Meetings" : 15
    "Documentation" : 10
    "Code Review" : 5
```

## Full Documentation

[Mermaid Pie Chart Docs](https://mermaid.js.org/syntax/pie.html)
