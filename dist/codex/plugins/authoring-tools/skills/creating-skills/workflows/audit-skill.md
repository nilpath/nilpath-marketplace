# Workflow: Audit a Skill

## Required Reading

Read these reference files before starting:
1. references/recommended-structure.md
2. references/skill-structure.md
3. references/core-principles.md
4. references/authoring-targets.md
5. references/official-spec.md

## Process

### Step 1: List Available Skills

Use the supplied skill path when provided. Otherwise ask whether to inspect workspace or personal skills; follow `references/authoring-targets.md` for the active client's discovery roots. Enumerate only the selected scope and show full paths if names collide.

Present skills as a numbered list in chat rather than a fixed-choice dialog that may truncate a long list. Record the selected absolute path as `SKILL_DIR`; audit in place without creating duplicate copies.

Present as:
```
Available skills:
1. creating-agents
2. creating-skills
3. manage-stripe
...
```

Ask: "Which skill would you like to audit? (enter number or name)"

### Step 2: Read the Skill

After user selects, read the full skill structure:

```bash
# Read main file
cat "$SKILL_DIR/SKILL.md"

# Check for workflows and references
ls "$SKILL_DIR"
ls "$SKILL_DIR/workflows" 2>/dev/null
ls "$SKILL_DIR/references" 2>/dev/null
```

Also read templates, scripts, and any invocation-policy sidecar. For explicitly selected marketplace sources, inspect `SKILL.md.j2` and render each requested target before applying native checks.

### Step 3: Run Audit Checklist

Evaluate against each criterion:

#### YAML Frontmatter

- [ ] Has `name:` field (lowercase-with-hyphens, max 64 chars)
- [ ] Unprefixed name matches directory name
- [ ] Has `description:` field
- [ ] Description says what it does AND when to use it
- [ ] Description is third person (not "I can..." or "You can...")
- [ ] Description is non-empty and at most 1,024 characters
- [ ] Invocation policy matches the user's intent using the active client's supported mechanism
- [ ] Explicit-only authoring tools have not made every output skill explicit-only by accident
- [ ] Native metadata contains no canonical source fields or unsupported client fields

#### Structure

- [ ] Body uses standard markdown headings — no XML tags (`<objective>`, `<quick_start>`, etc.)
- [ ] `SKILL.md` under 500 lines
- [ ] Has a Quick Start or equivalent immediate guidance section
- [ ] Has success criteria or guidelines section

#### Router Pattern (if complex skill)

- [ ] Essential principles inline in `SKILL.md` (not in separate file)
- [ ] Has intake question
- [ ] Has routing table
- [ ] All referenced workflow files exist
- [ ] All referenced reference files exist

#### Workflows (if present)

- [ ] Each has a Required Reading section
- [ ] Each has a Process section
- [ ] Each has a Success Criteria section
- [ ] Required reading references exist

#### Content Quality

- [ ] Principles are actionable (not vague platitudes)
- [ ] Steps are specific (not "do the thing")
- [ ] Success criteria are verifiable
- [ ] No redundant content across files
- [ ] No duplicate discovery copies or unnecessary command/prompt files
- [ ] Inputs and resource execution use the active client's mechanism, not another client's substitutions
- [ ] Scripts resolve from the selected skill folder and honor ordinary tool approvals

### Step 4: Generate Report

Present findings as:

```
## Audit Report: {skill-name}

### ✅ Passing
- [list passing items]

### ⚠️ Issues Found
1. **[Issue name]**: [Description]
   → Fix: [Specific action]

2. **[Issue name]**: [Description]
   → Fix: [Specific action]

### 📊 Score: X/Y criteria passing
```

### Step 5: Offer Fixes

If issues found, ask:
"Would you like me to fix these issues?"

Options:
1. **Fix all** — Apply all recommended fixes
2. **Fix one by one** — Review each fix before applying
3. **Just the report** — No changes needed

If fixing:
- Confirm the selected paths and requested changes before overwriting existing files
- Make each change
- Verify file validity after each change
- Report what was fixed

## Common Anti-Patterns to Flag

- **XML tags in body** — Using `<objective>`, `<quick_start>`, `<process>`, etc. instead of markdown headings
- **Skippable principles** — Essential principles in separate file instead of inline in `SKILL.md`
- **Monolithic skill** — Single file over 500 lines
- **Mixed concerns** — Procedures and knowledge in same file
- **Vague steps** — "Handle the error appropriately"
- **Untestable criteria** — "User is satisfied"
- **Missing routing** — Complex skill without intake/routing
- **Broken references** — Files mentioned but don't exist
- **Redundant content** — Same information in multiple places
- **Duplicate entrypoints** — A redundant command/prompt file or second discovery copy of the same skill
- **Incorrect invocation control** — An output intended to be explicit-only still auto-loads, or an output intended for discovery is unnecessarily restricted
- **Source/native confusion** — Native SKILL.md containing `targets`, canonical tools, or unrendered Jinja

## Success Criteria

Audit is complete when:
- [ ] Skill fully read and analyzed
- [ ] All checklist items evaluated
- [ ] Active-client invocation mode, metadata, and resource paths verified
- [ ] Report presented to user
- [ ] Fixes applied (if requested)
- [ ] User has clear picture of skill health
