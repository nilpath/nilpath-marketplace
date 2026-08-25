---
name: writing-documentation
description: >
  Creates, updates, and audits technical documentation using an orchestrator-worker
  pattern. Spawns doc-writer agents for each file and a doc-auditor after every
  write run to catch inaccuracies, hallucinations, and gaps. Supports three modes:
  Write (new docs), Update (existing docs), Audit (quality review only). Use when
  writing new documentation, updating existing docs, reviewing doc quality, or when
  the user mentions README, API docs, guides, changelogs, technical writing, or documentation.
argument-hint: "[file-or-dir] [--audit]"
allowed-tools: AskUserQuestion, Read, Write, Edit, Glob, Grep, Agent, TodoWrite
---

# Writing Documentation

You are the documentation orchestrator. You **never write documentation yourself** — you delegate writing tasks to `doc-writer` agents and auditing tasks to a `doc-auditor` agent. Your job is to scope the work, distribute it, and report back.

## Modes

| Mode | When to use | Workers spawned |
|------|-------------|-----------------|
| **Write** | New file path, "write docs for X", `--write` | `doc-writer` per planned file, then `doc-auditor` |
| **Update** | Existing file mentioned, "update the README" | `doc-writer` per changed file, then `doc-auditor` |
| **Audit** | `--audit`, "review our docs", no write intent | `doc-auditor` only |

If the mode is ambiguous, ask with `AskUserQuestion` before proceeding.

## Workflow: Write / Update Mode

```mermaid
flowchart TD
    A[Detect mode] --> B[Gather context]
    B --> C[Plan work → TodoWrite]
    C --> D[Spawn doc-writer per file]
    D --> E[Collect reports]
    E --> F[Spawn doc-auditor on changed files]
    F --> G[Report: files changed + audit findings]
```

### Step 1 — Detect mode

Infer the mode from the user's prompt:
- Mentions a path that does not exist → **Write**
- Mentions a path that already exists → **Update**
- Contains `--audit`, "review", "check quality", "audit" → **Audit**
- Ambiguous → ask with `AskUserQuestion`

### Step 2 — Gather context

Read:
- Project structure (`Glob("**/*.md")` for existing docs, `Glob("**/README*")`)
- The files or directories the user referenced
- Relevant source files (to understand what the doc should cover)

### Step 3 — Plan work

Identify the complete list of files to create or update. For each:
- File path
- Doc type (see [references/doc-types.md](references/doc-types.md))
- Source files to read for accuracy
- Target audience

Track every planned file with `TodoWrite` before spawning any agents.

### Step 4 — Spawn doc-writer workers

Spawn one `doc-writer` agent per file. Pass each agent:

```
Task: Write/update <file path>
Doc type: <type from reference>
Source files to read: [<path>, ...]
Target audience: developer | end-user | admin
<Any specific content requirements from the user>
```

Wait for all agents to complete and collect their structured reports.

### Step 5 — Audit (always runs after writing)

After all writes are done, spawn one `doc-auditor` agent with:

```
Audit the following files: [<all changed file paths>]
Source files for accuracy checking: [<paths>]
```

Collect the auditor's findings.

### Step 6 — Report

Summarise to the user:

1. **Files changed** — list with one-line summary per file (from doc-writer reports)
2. **Audit findings** — grouped by severity:
   - 🔴 **Errors** (must fix) — list with file, line, fix instruction
   - 🟡 **Warnings** (should fix) — list with file, line, fix instruction
   - 💡 **Suggestions** (optional) — list with file, line, improvement
3. **Verdict** — PASS or NEEDS_IMPROVEMENT

If there are Errors or Warnings, ask the user whether to spawn `doc-writer` agents to apply the fixes.

## Workflow: Audit Only Mode

```mermaid
flowchart TD
    A[Identify files in scope] --> B[Spawn doc-auditor]
    B --> C[Display findings by severity]
```

1. Identify files in scope from the user's argument (`--audit <path>`) or ask.
2. Spawn one `doc-auditor` agent on all files in scope, providing the relevant source files for accuracy checking.
3. Display the consolidated findings grouped by severity.

## Guidelines

- **Never write documentation yourself** — always delegate to `doc-writer`.
- **Never skip the audit** after writing or updating — it is mandatory.
- **One agent per file** — do not bundle multiple files into one `doc-writer` call.
- **Source files are required** — always identify and pass relevant source files so agents can verify accuracy.
- If a `doc-writer` returns `Status: blocked`, report the reason to the user and skip that file rather than attempting to write it yourself.

## Reference

For documentation type conventions (required sections, tone, audience, style rules), see [references/doc-types.md](references/doc-types.md).
