# Orchestration Patterns

Multi-agent orchestration patterns for complex workflows. Based on Anthropic's research system and industry best practices.

## When to Use Multi-Agent

**Single agent is sufficient when:**
- Task is isolated to known files
- One type of expertise needed
- Simple sequential steps
- Context fits in one conversation

**Multi-agent is valuable when:**
- Tasks can run in parallel
- Different expertise areas needed
- Verbose operations would consume context
- Complex decomposition required

**Warning:** Don't use multi-agent prematurely. A single well-designed agent handles most tasks effectively. Multi-agent adds coordination complexity.

## Pattern 1: Fan-Out (Parallel Research)

Multiple agents explore different areas simultaneously, then results are synthesized.

### When to Use

- Independent research tasks
- Codebase exploration across modules
- Documentation gathering from multiple sources
- Any task where subtasks don't depend on each other

### Example Request

```
Research the authentication, database, and API modules in parallel using separate subagents
```

### How It Works

```
┌─────────────┐
│ Orchestrator│
└──────┬──────┘
       │ spawns
  ┌────┼────┐
  ▼    ▼    ▼
┌───┐┌───┐┌───┐
│ A ││ B ││ C │  (parallel exploration)
└─┬─┘└─┬─┘└─┬─┘
  │    │    │
  └────┼────┘
       ▼
┌─────────────┐
│  Synthesis  │
└─────────────┘
```

### Agent Design for Fan-Out

Each agent should:
- Have a clear, bounded scope
- Return structured summaries (not raw data)
- Handle missing information gracefully

### Benefits

- Cut research time by up to 90% for complex queries
- Each agent maintains focused context
- Only summaries return to main conversation

### Risks

- Results returning can consume main context
- Agents may duplicate work without clear boundaries
- Synthesis step requires good task descriptions

## Pattern 2: Pipeline (Sequential Processing)

Agents process in sequence, each building on previous results.

### When to Use

- Review-then-fix workflows
- Multi-stage validation
- Transformation chains
- Any task with clear dependencies

### Example Request

```
First use code-reviewer to find issues, then use debugger to fix the critical ones
```

### How It Works

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Stage 1 │ ──▶ │ Stage 2 │ ──▶ │ Stage 3 │
│ Review  │     │  Fix    │     │ Verify  │
└─────────┘     └─────────┘     └─────────┘
    │               │               │
    ▼               ▼               ▼
  Issues         Fixes         Confirmation
```

### Agent Design for Pipeline

- **Clear output contracts** - Each stage produces well-defined output
- **Error handling** - Each stage handles upstream failures
- **Resumability** - Can restart from any stage

### Example Pipeline: Review → Fix → Test

**Stage 1: Reviewer**
```yaml
name: pipeline-reviewer
description: First stage of review pipeline
tools: Read, Grep, Glob
```

```markdown
Review code and output a structured list of issues:

## Issues Found

### Critical
- [file:line] Description of issue

### Warning
- [file:line] Description of issue
```

**Stage 2: Fixer**
```yaml
name: pipeline-fixer
description: Second stage of review pipeline
tools: Read, Write, Edit, Bash
```

```markdown
Fix issues from the review stage. For each issue:
1. Navigate to the file and line
2. Apply the fix
3. Document what was changed
```

**Stage 3: Verifier**
```yaml
name: pipeline-verifier
description: Final stage of review pipeline
tools: Read, Bash
```

```markdown
Verify fixes were applied correctly:
1. Run tests
2. Check each fixed location
3. Confirm no regressions
```

### Benefits

- Clear separation of concerns
- Each stage can use specialized tools
- Easy to debug individual stages

### Risks

- Error propagation through stages
- Latency from sequential processing
- Context may be lost between stages

## Pattern 3: Orchestrator-Worker

A lead agent decomposes tasks and delegates to specialist workers.

### When to Use

- Complex features with multiple components
- Tasks requiring dynamic decomposition
- Large-scale refactoring
- When subtask structure isn't known upfront

### Example Request

```
Implement the user authentication feature based on this spec
```

### How It Works

```
┌──────────────────┐
│   Orchestrator   │
│   (decomposes)   │
└────────┬─────────┘
         │ delegates
    ┌────┼────┬────┐
    ▼    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐┌─────┐
│Model││Auth ││API  ││UI   │
│Agent││Agent││Agent││Agent│
└──┬──┘└──┬──┘└──┬──┘└──┬──┘
   │      │      │      │
   └──────┼──────┼──────┘
          ▼
   ┌─────────────────┐
   │   Integration   │
   └─────────────────┘
```

### Task Decomposition

The orchestrator must provide each worker with:
- **Objective**: Clear statement of what to accomplish
- **Output format**: How to structure results
- **Tool guidance**: Which tools and sources to use
- **Boundaries**: What is and isn't in scope

Without detailed task descriptions, agents duplicate work, leave gaps, or fail to find necessary information.

### Example Orchestrator Prompt

```markdown
You are a lead developer orchestrating a feature implementation.

When given a feature request:
1. Analyze requirements and identify components
2. Decompose into discrete, bounded tasks
3. Delegate each task to appropriate specialist

For each delegation, provide:
- Clear objective statement
- Expected output format
- Relevant context from the codebase
- Scope boundaries (what NOT to do)

After all tasks complete:
- Review results for consistency
- Integrate components
- Verify end-to-end functionality
```

### Worker Agent Design

Workers should be specialized and focused:

```yaml
name: auth-implementer
description: Implements authentication components. Use when orchestrator needs auth work.
tools: Read, Write, Edit, Bash, Glob, Grep
```

```markdown
You are an authentication specialist.

When delegated a task:
1. Understand the specific objective
2. Research existing auth patterns in the codebase
3. Implement following established conventions
4. Document your changes
5. Return a summary of what was implemented
```

### Benefits

- Handles complexity through decomposition
- Specialists can focus on their domain
- Orchestrator maintains big picture

### Risks

- Orchestration complexity
- Communication overhead
- Coordination failures

## Scaling Guidelines

Match agent count to task complexity:

| Task Type | Agents | Tool Calls |
| --------- | ------ | ---------- |
| Simple fact-finding | 1 | 3-10 |
| Direct comparison | 2-4 | 10-30 |
| Complex research | 5-10 | 30-100 |
| Major implementation | 10+ | 100+ |

## Best Practices

### 1. Start Simple

Begin with a single well-designed agent. Add more only when you hit clear limitations.

### 2. Define Clear Boundaries

Each agent should have explicit scope. Overlapping responsibilities cause duplication.

### 3. Structured Output

Design agents to return structured summaries, not raw dumps. This preserves context in the orchestrator.

### 4. Error Handling

Each agent should handle failures gracefully and return useful information even when it can't complete the task.

### 5. Test Incrementally

Test each agent in isolation before combining. Multi-agent bugs are harder to diagnose.

## Common Mistakes

### Mistake 1: Over-decomposition

Breaking tasks too finely creates coordination overhead that exceeds the benefit.

**Bad:** 10 agents for a simple feature
**Good:** 2-3 agents for a complex feature

### Mistake 2: Missing Context

Agents without sufficient context make poor decisions or duplicate effort.

**Bad:** "Research authentication"
**Good:** "Research JWT authentication patterns in src/auth/, focusing on token refresh logic"

### Mistake 3: No Synthesis Plan

Launching parallel agents without a plan to integrate results.

**Bad:** Fan-out with no clear next step
**Good:** Fan-out with explicit synthesis instructions
