# Workflow: Get Guidance on Skill Design

<required_reading>
**Read these reference files NOW:**
1. references/core-principles.md
2. references/recommended-structure.md
3. references/authoring-targets.md
</required_reading>

<process>
## Step 1: Understand the Problem Space

Ask the user:
- What task or domain are you trying to support?
- Is this something you do repeatedly?
- What makes it complex enough to need a skill?
- Is the desired output a native skill for the active client (default), or explicitly a marketplace source?
- Should it be workspace-scoped or personal, and automatically discoverable or explicit-only?

## Step 2: Determine If a Skill Is Right

**Create a skill when:**
- Task is repeated across multiple sessions
- Domain knowledge doesn't change frequently
- Complex enough to benefit from structure
- Would save significant time if automated

**Don't create a skill when:**
- One-off task (just do it directly)
- Changes constantly (will be outdated quickly)
- Too simple (overhead isn't worth it)
- Better as a one-off prompt or an always-on instruction rather than a reusable workflow

Share this assessment with user.

## Step 3: Map the Workflows

Ask: "What are the different things someone might want to do with this skill?"

Common patterns:
- Create / Read / Update / Delete
- Build / Debug / Ship
- Setup / Use / Troubleshoot
- Import / Process / Export

Each distinct workflow = potential workflow file.

## Step 4: Identify Domain Knowledge

Ask: "What knowledge is needed regardless of which workflow?"

This becomes references:
- API patterns
- Best practices
- Common examples
- Configuration details

## Step 5: Draft the Structure

Based on answers, recommend structure:

**If 1 workflow, simple knowledge:**
```
skill-name/
└── SKILL.md (everything in one file)
```

**If 2+ workflows, shared knowledge:**
```
skill-name/
├── SKILL.md (router)
├── workflows/
│   ├── workflow-a.md
│   └── workflow-b.md
└── references/
    └── shared-knowledge.md
```

## Step 6: Identify Essential Principles

Ask: "What rules should ALWAYS apply, no matter which workflow?"

These become `## Essential Principles` in SKILL.md.

Examples:
- "Always verify before reporting success"
- "Never store credentials in code"
- "Ask before making destructive changes"

## Step 7: Present Recommendation

Summarize:
- Recommended structure (simple vs router pattern)
- List of workflows
- List of references
- Essential principles
- Native placement and invocation policy, following the existing project convention without duplicate copies

Ask: "Does this structure make sense? Ready to build it?"

If yes → offer to switch to "Create a new skill" workflow
If no → clarify and iterate
</process>

<decision_framework>
## Quick Decision Framework

| Situation | Recommendation |
|-----------|----------------|
| Single task, repeat often | Simple skill |
| Multiple related tasks | Router + workflows |
| Complex domain, many patterns | Router + workflows + references |
| Reusable, user-triggered task | Explicit-only skill using the active client's invocation policy |
| Always-on conventions | Client instruction file rather than a relevance-loaded skill |
| One-off task | No skill needed |
</decision_framework>

<success_criteria>
Guidance is complete when:
- [ ] User understands if they need a skill
- [ ] Structure is recommended and explained
- [ ] Workflows are identified
- [ ] References are identified
- [ ] Essential principles are identified
- [ ] User is ready to build (or decided not to)
</success_criteria>
