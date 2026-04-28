# Workflow: Audit a Skill

## Required Reading

Read these reference files before starting:
1. references/recommended-structure.md
2. references/skill-structure.md
3. references/core-principles.md

## Process

### Step 1: List Available Skills

**DO NOT use AskUserQuestion** — there may be many skills.

Enumerate skills in chat as numbered list:

```bash
ls ~/.claude/skills/
```

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
cat ~/.claude/skills/{skill-name}/SKILL.md

# Check for workflows and references
ls ~/.claude/skills/{skill-name}/
ls ~/.claude/skills/{skill-name}/workflows/ 2>/dev/null
ls ~/.claude/skills/{skill-name}/references/ 2>/dev/null
```

### Step 3: Run Audit Checklist

Evaluate against each criterion:

#### YAML Frontmatter

- [ ] Has `name:` field (lowercase-with-hyphens, max 64 chars)
- [ ] Name matches directory name
- [ ] Has `description:` field
- [ ] Description says what it does AND when to use it
- [ ] Description is third person (not "I can..." or "You can...")
- [ ] `disable-model-invocation: true` set if skill has side effects (deploy, commit, send)

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
- [ ] No `.claude/commands/` file created separately (skill name IS the slash command)

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
- **Separate command file** — A `.claude/commands/{name}.md` created alongside the skill
- **Side-effect skill without invocation control** — Deploy/commit/send skills without `disable-model-invocation: true`

## Success Criteria

Audit is complete when:
- [ ] Skill fully read and analyzed
- [ ] All checklist items evaluated
- [ ] Report presented to user
- [ ] Fixes applied (if requested)
- [ ] User has clear picture of skill health
