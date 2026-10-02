# Workflow: Create a New Skill

## Required Reading

Read these reference files before starting:
1. references/recommended-structure.md
2. references/skill-structure.md
3. references/core-principles.md

## Process

### Step 1: Adaptive Requirements Gathering

**If user provided context** (e.g., "build a skill for X"):
→ Analyze what's stated, what can be inferred, what's unclear
→ Skip to asking about genuine gaps only

**If user just invoked skill without context:**
→ Ask what they want to build

#### Using AskUserQuestion

Ask 2-4 domain-specific questions based on actual gaps. Each question should:
- Have specific options with descriptions
- Focus on scope, complexity, outputs, boundaries
- NOT ask things obvious from context

Example questions:
- "What specific operations should this skill handle?" (with options based on domain)
- "Should this also handle [related thing] or stay focused on [core thing]?"
- "What should the user see when successful?"
- "Should Claude invoke this automatically, or should you trigger it manually?" (→ determines `disable-model-invocation`)

#### Decision Gate

After initial questions, ask:
"Ready to proceed with building, or would you like me to ask more questions?"

Options:
1. **Proceed to building** - I have enough context
2. **Ask more questions** - There are more details to clarify
3. **Let me add details** - I want to provide additional context

### Step 2: Research Trigger (If External API)

**When external service detected**, ask using AskUserQuestion:
"This involves [service name] API. Would you like me to research current endpoints and patterns before building?"

Options:
1. **Yes, research first** - Fetch current documentation for accurate implementation
2. **No, proceed with general patterns** - Use common patterns without specific API research

If research requested:
- Use Context7 MCP to fetch current library documentation
- Or use WebSearch for recent API documentation
- Focus on 2024-2026 sources
- Store findings for use in content generation

### Step 3: Choose Invocation Mode

Ask whether Claude should be able to invoke this skill automatically:

**Claude-invoked (default):** Claude loads the skill when relevant. Use for reference content, guidelines, domain knowledge.

**Manual-only** (`disable-model-invocation: true`): Only you trigger it with `/skill-name`. Use for side-effect workflows (deploy, commit, send messages, destructive operations).

**Background-only** (`user-invocable: false`): Claude applies it automatically but it's hidden from the `/` menu. Use for always-on conventions and style guides.

### Step 4: Decide Structure

**Simple skill (single workflow, <200 lines):**
→ Single `SKILL.md` file with all content

**Complex skill (multiple workflows OR domain knowledge):**
→ Router pattern:

```
skill-name/
├── SKILL.md (router + principles)
├── workflows/ (procedures — follow these)
├── references/ (knowledge — read when needed)
├── templates/ (output structures — copy and fill)
└── scripts/ (reusable code — execute)
```

Factors favoring router pattern:
- Multiple distinct user intents (create vs debug vs ship)
- Shared domain knowledge across workflows
- Essential principles that must not be skipped
- Skill likely to grow over time

**Consider `templates/` when:**
- Skill produces consistent output structures (plans, specs, reports)
- Structure matters more than creative generation

**Consider `scripts/` when:**
- Same code runs across invocations (deploy, setup, API calls)
- Operations are error-prone when rewritten each time

See references/recommended-structure.md for templates.

### Step 5: Create Directory

```bash
mkdir -p ~/.claude/skills/{skill-name}
# If complex:
mkdir -p ~/.claude/skills/{skill-name}/workflows
mkdir -p ~/.claude/skills/{skill-name}/references
# If needed:
mkdir -p ~/.claude/skills/{skill-name}/templates
mkdir -p ~/.claude/skills/{skill-name}/scripts
```

### Step 6: Write SKILL.md

Use the template from [templates/simple-skill.md](../templates/simple-skill.md) or [templates/router-skill.md](../templates/router-skill.md).

**Simple skill:** Write complete skill file with:
- YAML frontmatter (`name`, `description`, and any invocation control fields)
- `## Quick Start` with immediate actionable example
- `## Instructions` with core guidance
- `## Examples` with input/output pairs
- `## Guidelines` with rules and constraints

**Complex skill:** Write router with:
- YAML frontmatter
- `## Essential Principles` (inline, always loaded)
- `## What Would You Like To Do?` (intake question)
- `## Routing` table (maps answers to workflows)
- `## Reference Index` and `## Workflows Index`

**Body format:** Standard markdown headings only. No XML tags.

### Step 7: Write Workflows (if complex)

For each workflow file:

```markdown
# Workflow: Name

## Required Reading

Read these reference files before starting:
1. references/relevant-file.md

## Process

### Step 1: Name
What to do.

### Step 2: Name
What to do.

## Success Criteria

This workflow is complete when:
- [ ] Criterion 1
- [ ] Criterion 2
```

### Step 8: Write References (if needed)

Domain knowledge that:
- Multiple workflows might need
- Doesn't change based on workflow
- Contains patterns, examples, technical details

### Step 9: Validate Structure

Check:
- [ ] YAML frontmatter valid
- [ ] `name` matches directory (lowercase-with-hyphens)
- [ ] `description` says what it does AND when to use it (third person)
- [ ] Body uses markdown headings — no XML tags
- [ ] `disable-model-invocation: true` set if skill has side effects
- [ ] All referenced files exist
- [ ] `SKILL.md` under 500 lines
- [ ] No separate `.claude/commands/` file created (the skill name IS the slash command)

### Step 10: Test

Invoke the skill and observe:
- Does it load when expected (or stay hidden as intended)?
- Does it ask the right intake question?
- Does it load the right workflow?
- Does the workflow load the right references?
- Does output match expectations?

Iterate based on real usage, not assumptions.

## Success Criteria

Skill is complete when:
- [ ] Requirements gathered with appropriate questions
- [ ] Invocation mode chosen (`disable-model-invocation`, `user-invocable`, or default)
- [ ] API research done if external service involved
- [ ] Directory structure correct
- [ ] `SKILL.md` has valid frontmatter
- [ ] Essential principles inline (if complex skill)
- [ ] Intake question routes to correct workflow (if router)
- [ ] All workflows have Required Reading + Process + Success Criteria
- [ ] References contain reusable domain knowledge
- [ ] Tested with real invocation
