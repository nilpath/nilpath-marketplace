# Workflow: Add a Template to a Skill

<required_reading>
**Read these reference files NOW:**
1. references/using-templates.md
2. references/authoring-targets.md
</required_reading>

<process>
## Step 1: Identify the Skill

Ask (if not already provided):
- Which skill needs a template?
- What output does this template structure?

Use the supplied path or ask for workspace versus personal scope, then select one active-client location using `references/authoring-targets.md`. Record the absolute path as `SKILL_DIR` and edit in place without duplicating the skill.

## Step 2: Analyze Template Need

Confirm this is a good template candidate:
- [ ] Output has consistent structure across uses
- [ ] Structure matters more than creative generation
- [ ] Filling placeholders is more reliable than blank-page generation

If not a good fit, suggest alternatives (workflow guidance, reference examples).

## Step 3: Create Templates Directory

```bash
mkdir -p "$SKILL_DIR/templates"
```

## Step 4: Design Template Structure

Gather requirements:
- What sections does the output need?
- What information varies between uses? (→ placeholders)
- What stays constant? (→ static structure)

## Step 5: Write Template File

Create `templates/{template-name}.md` under `SKILL_DIR`, confirming before overwriting existing resources or workflows. Preserve the skill's invocation policy. In opt-in marketplace-source mode, protect literal template placeholders with raw guards if this file itself needs Jinja rendering; otherwise keep it a verbatim `.md`.

Include:
- Clear section markers
- `{{PLACEHOLDER}}` syntax for variable content
- Brief inline guidance where helpful
- Minimal example content

## Step 6: Update Workflow to Use Template

Find the workflow that produces this output. Add:
```markdown
## Process
...
N. Resolve and read `templates/{template-name}.md` from this skill directory.
N+1. Copy template structure
N+2. Fill each placeholder based on gathered context
...
```

## Step 7: Test

Invoke the skill workflow and verify:
- Template is read at the right step
- All placeholders get filled appropriately
- Output structure matches template
- No placeholders left unfilled
- All resource links resolve from the selected skill directory
</process>

<success_criteria>
Template is complete when:
- [ ] templates/ directory exists
- [ ] Template file has clear structure with placeholders
- [ ] At least one workflow references the template
- [ ] Workflow instructions explain when/how to use template
- [ ] Tested with real invocation
</success_criteria>
