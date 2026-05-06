---
name: executing-plan
description: Executes an approved implementation plan produced by the planning skill. Creates a git worktree, critically reviews the plan for blockers, tracks tasks via TodoWrite, and delegates each task to the right subagent one at a time. Runs code-reviewer after every task and a final holistic review before creating a PR. Use after /planning produces an approved plan.md.
argument-hint: '"[feature-path]" (e.g. "docs/features/001-oauth")'
allowed-tools: AskUserQuestion, Read, Glob, Grep, Agent, TodoWrite, Skill(git-commits), Skill(using-git-worktrees), Bash(gh pr create *)
---

# Executing Plan

Execute an approved `plan.md` produced by the `planning` skill. A dedicated git worktree is created upfront, tasks are implemented one at a time with a code-reviewer pass after each commit, and a final holistic review runs before the PR is created.

Do **NOT** write implementation code directly — all code work is delegated to subagents.

## Quick Start

1. Have an approved `docs/features/<NNN>-<slug>/plan.md` ready
2. Invoke: `/executing-plan docs/features/<NNN>-<slug>`

## Process Flow

```mermaid
flowchart TD
    A([Start]) --> W[Create git worktree\nSkill using-git-worktrees]
    W --> B[Read plan.md]
    B --> C[Critical review\nscan for blockers]
    C --> D{Blockers?}
    D -- Yes --> E[Raise via AskUserQuestion\none question per blocker type]
    E --> F{Resolved?}
    F -- No --> G([Abort])
    F -- Yes --> H[Initialize TodoWrite\none entry per task]
    D -- No --> H
    H --> TASK

    subgraph TASK[Execute Task]
        direction TD
        T1[Determine agent] --> T2[Spawn implementation agent\nfull task block + feature path]
        T2 --> T3[Wait for commit]
        T3 --> T4[Spawn code-reviewer\nmodified files + task context]
        T4 --> T5{Issues found?}
        T5 -- Yes --> T6[Respawn implementation agent\nwith review feedback]
        T6 --> T7[Mark task complete]
        T5 -- No --> T7
    end

    TASK --> Q{More tasks?}
    Q -- Yes --> TASK
    Q -- No --> R[Final code-reviewer\nentire feature directory]
    R --> S[Skill git-commits + gh pr create]
    S --> CL{Clean up worktree?}
    CL -- Yes --> RM[Skill using-git-worktrees\nremove worktree]
    CL -- No --> Z
    RM --> Z([Done])
```

**Critical review — scan for these blockers before starting:**

- `[AMBIGUOUS: ...]` markers left by the task-decomposer
- Placeholder `<test-command>` or `path/to/` not yet filled in
- Files or modules referenced that do not exist yet
- Tasks with more than 10 steps (ask whether to split)
- Missing tech stack details (test runner unspecified, language version unknown)

Present all blockers in a single `AskUserQuestion` — one question per blocker type.

## Agent Selection

Read the task title, description, steps, and file list — then reason about what the task is fundamentally about:

| Agent | Use when |
|-------|----------|
| `python-task-agent` | Writing or modifying Python source code |
| `coding-task-agent` | Writing or modifying source code in any other language |
| `technical-writer` | Documentation, READMEs, changelogs only — no executable code |
| `code-debugger` | Diagnosing and fixing a broken or failing implementation |

Do not reduce this to file extension matching. A `.md` update involving technical decisions belongs to `coding-task-agent`. A Python script generating documentation output may suit `technical-writer`.

`technical-writer` tasks skip the code-reviewer step.

## Remember

- **ALWAYS implement one task at a time** — never bundle multiple tasks into a single agent call
- **ALWAYS follow the Execute Task subflow for every task** — do not skip the code-reviewer step
- Never write implementation code yourself — delegate all code work to subagents
- When spawning implementation agents: pass the **full task block verbatim** + absolute path to the feature directory + any blocker resolutions
- When spawning code-reviewer: pass the **list of modified files** + brief context ("Review Task NNN: [title]")
- If an agent returns without a commit (nothing changed), report it to the user and move on — do not block
- If the plan has no `### Task NNN:` blocks, stop and inform the user the plan is empty or malformed
- Keep the user informed with brief status updates between tasks ("Executing Task 003: implement parse_token…")

## When to Stop and Ask for Help

Stop and use `AskUserQuestion` if:

- You hit a blocker (missing dependency, tests fail, instruction unclear)
- The plan has critical gaps preventing you from starting
- You don't understand an instruction
- Verification fails repeatedly
