# Workflow: Upgrade Skill to Router Pattern

<required_reading>
**Read these reference files NOW:**
1. references/recommended-structure.md
2. references/skill-structure.md
3. references/authoring-targets.md
4. references/invocation-and-arguments.md
</required_reading>

<process>
## Step 1: Select the Skill

Use the supplied skill path, or ask for workspace versus personal scope and enumerate the active client's locations from `references/authoring-targets.md`. Resolve one selected absolute path as `SKILL_DIR`. Do not move the skill or create a duplicate copy.

Present numbered list, ask: "Which skill should be upgraded to the router pattern?"

## Step 2: Verify It Needs Upgrading

Read the skill:
```bash
cat "$SKILL_DIR/SKILL.md"
ls "$SKILL_DIR"
```

**Already a router?** (has workflows/ and intake question)
→ Tell user it's already using router pattern, offer to add workflows instead

**Simple skill that should stay simple?** (under 200 lines, single workflow)
→ Explain that router pattern may be overkill, ask if they want to proceed anyway

**Good candidate for upgrade:**
- Over 200 lines
- Multiple distinct use cases
- Essential principles that shouldn't be skipped
- Growing complexity

## Step 3: Identify Components

Analyze the current skill and identify:

1. **Essential principles** - Rules that apply to ALL use cases
2. **Distinct workflows** - Different things a user might want to do
3. **Reusable knowledge** - Patterns, examples, technical details

Present findings:
```
## Analysis

**Essential principles I found:**
- [Principle 1]
- [Principle 2]

**Distinct workflows I identified:**
- [Workflow A]: [description]
- [Workflow B]: [description]

**Knowledge that could be references:**
- [Reference topic 1]
- [Reference topic 2]
```

Ask: "Does this breakdown look right? Any adjustments?"

## Step 4: Create Directory Structure

Confirm before rewriting existing files. Preserve the current client, native metadata, invocation policy (including any sidecar), inputs, and resource execution semantics. In explicitly requested marketplace-source mode, update `.j2` sources and inspect rendered outputs instead of replacing sources with native files.

```bash
mkdir -p "$SKILL_DIR/workflows" "$SKILL_DIR/references"
```

## Step 5: Extract Workflows

For each identified workflow:

1. Create `workflows/{workflow-name}.md`
2. Add a Required Reading section (references it needs)
3. Add a Process section (steps from original skill)
4. Add a Success Criteria section

## Step 6: Extract References

For each identified reference topic:

1. Create `references/{reference-name}.md`
2. Move relevant content from original skill
3. Structure with descriptive Markdown headings

## Step 7: Rewrite SKILL.md as Router

Use the following native router skeleton, retaining all supported existing metadata and invocation policy, not just the two shown fields:

```markdown
---
name: skill-name
description: "Replace with the existing description."
---

## Essential Principles
[Extracted principles - inline, cannot be skipped]

## What Would You Like To Do?
**Ask the user:**

What would you like to do?
1. [Workflow A option]
2. [Workflow B option]
...

**Wait for response before proceeding.**

## Routing
| Response | Workflow |
|----------|----------|
| 1, "keywords" | `workflows/workflow-a.md` |
| 2, "keywords" | `workflows/workflow-b.md` |

## Reference Index
[List all references by category]

## Workflows Index
| Workflow | Purpose |
|----------|---------|
| workflow-a.md | [What it does] |
| workflow-b.md | [What it does] |
```

## Step 8: Verify Nothing Was Lost

Compare original skill content against new structure:
- [ ] All principles preserved (now inline)
- [ ] All procedures preserved (now in workflows)
- [ ] All knowledge preserved (now in references)
- [ ] No orphaned content
- [ ] Existing invocation mode and native metadata preserved
- [ ] All links resolve from the selected skill; no discovery duplicates

## Step 9: Test

Invoke the upgraded skill:
- Does intake question appear?
- Does each routing option work?
- Do workflows load correct references?
- Does behavior match original skill?
- Does explicit versus automatic invocation still match the chosen policy?

Report any issues.
</process>

<success_criteria>
Upgrade is complete when:
- [ ] workflows/ directory created with workflow files
- [ ] references/ directory created (if needed)
- [ ] SKILL.md rewritten as router
- [ ] Essential principles inline in SKILL.md
- [ ] All original content preserved
- [ ] Intake question routes correctly
- [ ] Tested and working
</success_criteria>
