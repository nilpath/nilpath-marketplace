# Workflow: Add a Reference to Existing Skill

<required_reading>
**Read these reference files NOW:**
1. references/recommended-structure.md
2. references/skill-structure.md
3. references/authoring-targets.md
</required_reading>

<process>
## Step 1: Select the Skill

Use the supplied skill path, or ask for workspace versus personal scope and enumerate that scope's active-client locations from `references/authoring-targets.md`. Follow the existing convention and select one absolute `SKILL_DIR`; do not create duplicate discovery copies.

Present numbered list, ask: "Which skill needs a new reference?"

## Step 2: Analyze Current Structure

```bash
cat "$SKILL_DIR/SKILL.md"
ls "$SKILL_DIR/references" 2>/dev/null
```

Determine:
- **Has references/ folder?** → Good, can add directly
- **Simple skill?** → May need to create references/ first
- **What references exist?** → Understand the knowledge landscape

Report current references to user.

## Step 3: Gather Reference Requirements

Ask:
- What knowledge should this reference contain?
- Which workflows will use it?
- Is this reusable across workflows or specific to one?

**If specific to one workflow** → Consider putting it inline in that workflow instead.

## Step 4: Create the Reference File

Create `references/{reference-name}.md` under the selected `SKILL_DIR`. Confirm before overwriting an existing resource or updating the entrypoint. Preserve invocation policy. If editing marketplace sources explicitly, follow the source-only rules in `authoring-targets.md`; native references contain no Jinja.

Use descriptive Markdown headings:
```markdown
## Overview
Brief description of what this reference covers

## Common Patterns
[Reusable patterns, examples, code snippets]

## Guidelines
[Best practices, rules, constraints]

## Examples
[Concrete examples with explanation]
```

## Step 5: Update SKILL.md

Add the new reference to the Reference Index with a working link:
```markdown
**Category:** [existing.md](references/existing.md), [new-reference.md](references/new-reference.md)
```

## Step 6: Update Workflows That Need It

For each workflow that should use this reference:

1. Read the workflow file
2. Add to its Required Reading section
3. Verify the workflow still makes sense with this addition

## Step 7: Verify

- [ ] Reference file exists and is well-structured
- [ ] Reference is in SKILL.md reference_index
- [ ] Relevant workflows have it in required_reading
- [ ] No broken references
- [ ] Links resolve from the skill directory and no unrelated skill files were changed
</process>

<success_criteria>
Reference addition is complete when:
- [ ] Reference file created with useful content
- [ ] Added to reference_index in SKILL.md
- [ ] Relevant workflows updated to read it
- [ ] Content is reusable (not workflow-specific)
</success_criteria>
