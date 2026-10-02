# Common Patterns

Common patterns for skill authoring: templates, examples, terminology, and new features.

## Template Pattern

Provide output templates for consistent results. Match strictness to the task.

**Strict** — when output format must be exact:

```markdown
## Report Template

Use this exact structure:

```markdown
# [Analysis Title]

## Executive Summary
[One-paragraph overview of key findings]

## Key Findings
- Finding 1 with supporting data
- Finding 2 with supporting data

## Recommendations
1. Specific actionable recommendation
2. Specific actionable recommendation
```
```

**Flexible** — when Claude should adapt based on context:

```markdown
## Report Template

Here is a sensible default, but use your judgment:

```markdown
# [Analysis Title]

## Executive Summary
[Overview]

## Key Findings
[Adapt sections based on what you discover]

## Recommendations
[Tailor to the specific context]
```

Adjust sections as needed for the specific analysis type.
```

Use strict when: compliance reports, standardized formats, automated processing.
Use flexible when: exploratory analysis, context-dependent formatting, creative tasks.

## Examples Pattern

For skills where output quality depends on seeing examples, provide input/output pairs.

```markdown
## Commit Message Format

**Example 1:**
Input: Added user authentication with JWT tokens
Output:
```
feat(auth): implement JWT-based authentication

Add login endpoint and token validation middleware
```

**Example 2:**
Input: Fixed bug where dates displayed incorrectly in reports
Output:
```
fix(reports): correct date formatting in timezone conversion

Use UTC timestamps consistently across report generation
```

Follow this style: `type(scope): brief description`, then a detailed explanation.
```

Use examples when:
- Output format has nuances that text explanations can't capture
- Pattern recognition is easier than rule following
- Examples demonstrate edge cases
- Multi-shot learning improves quality

## Shell Injection Pattern

Inject live context into a skill before Claude sees it. Use when the skill needs current state.

```markdown
---
name: pr-summary
description: Summarize the current pull request
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## Pull Request Context

- Branch: !`git branch --show-current`
- Diff: !`gh pr diff`
- Changed files: !`gh pr diff --name-only`

## Task

Summarize this pull request for a reviewer who hasn't seen it yet.
```

> **Note:** When showing shell injection syntax as documentation inside a skill, add a space before the backtick (` ! \`cmd\` `) to prevent it executing during skill load.

See [invocation-and-arguments.md](invocation-and-arguments.md) for full details.

## Invocation Control Pattern

Use `disable-model-invocation: true` for side-effect workflows you want to trigger manually:

```yaml
---
name: deploy
description: Deploy the application to production
disable-model-invocation: true
allowed-tools: Bash(./scripts/deploy.sh *)
---

Deploy $ARGUMENTS to production:

1. Run the test suite
2. Build the application
3. Push to the deployment target
4. Verify the deployment succeeded
```

Claude will never suggest running `/deploy` automatically. Only you can trigger it.

Use `user-invocable: false` for background knowledge Claude applies automatically without prompting:

```yaml
---
name: api-conventions
description: API design patterns for this codebase. Apply when writing or reviewing API endpoints.
user-invocable: false
---
```

See [invocation-and-arguments.md](invocation-and-arguments.md) for the full invocation control matrix.

## Arguments Pattern

For skills that operate on a target, use `$ARGUMENTS` for simple cases and named arguments for clarity:

**Simple:**

```yaml
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
argument-hint: [issue-number]
---

Fix GitHub issue $ARGUMENTS following our coding standards.
```

**Named arguments:**

```yaml
---
name: migrate-component
description: Migrate a component between frameworks
arguments: [component, from, to]
argument-hint: [component] [from-framework] [to-framework]
---

Migrate the $component component from $from to $to.
Preserve all existing behavior and tests.
```

## Consistent Terminology

Choose one term and use it throughout. Inconsistent terminology confuses Claude and reduces quality.

**Good** — consistent usage:
- Always "API endpoint" (not mixing with "URL", "API route", "path")
- Always "field" (not mixing with "box", "element", "control")
- Always "extract" (not mixing with "pull", "get", "retrieve")

**Bad** — inconsistent usage creates confusion:
- Mix "API routes", "URLs", "paths", "endpoints" — are these the same?
- Mix "fields", "boxes", "elements", "controls" — Claude must guess

Implementation:
1. Choose terminology early in skill development
2. Document key terms in a `## Glossary` section if domain is specialized
3. Use find/replace to enforce consistency across all files

## Default with Escape Hatch

Provide one default approach with a single escape hatch for edge cases. Avoid offering many alternatives upfront — it creates decision paralysis.

**Good:**

```markdown
## Quick Start

Use pdfplumber for text extraction:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```

For scanned PDFs requiring OCR, use pdf2image with pytesseract instead.
```

**Bad** — too many options:

```markdown
## Quick Start

You can use any of these libraries:
- **pypdf**: Good for basic extraction
- **pdfplumber**: Better for tables
- **PyMuPDF**: Faster but more complex
- **pdf2image**: For scanned documents
```

Claude must now research and compare all options before starting.

## Progressive Disclosure Pattern

Keep `SKILL.md` concise by linking to reference files. Claude reads them only when needed.

```markdown
## Advanced Features

**Custom audiences**: See [audiences.md](audiences.md)
**Conversion tracking**: See [conversions.md](conversions.md)
**Budget optimization**: See [budgets.md](budgets.md)
**API reference**: See [api-reference.md](api-reference.md)
```

Benefits: `SKILL.md` stays under 500 lines, Claude only reads relevant references, token usage scales with task complexity.

## Validation Pattern

For skills with validation steps, make validation scripts verbose and specific.

```markdown
## Validation

After making changes, validate immediately:

```bash
python scripts/validate.py output_dir/
```

If validation fails, fix errors before continuing. Validation errors include:

- **Field not found**: "Field 'signature_date' not found. Available: customer_name, order_total"
- **Type mismatch**: "Field 'order_total' expects number, got string"
- **Missing required field**: "Required field 'customer_name' is missing"

Only proceed when validation passes with zero errors.
```

## Checklist Pattern

For complex multi-step workflows, provide a checklist Claude can copy and track.

```markdown
## Workflow

Copy this checklist and check off items as you complete them:

```
- [ ] Step 1: Analyze the form (run analyze_form.py)
- [ ] Step 2: Create field mapping (edit fields.json)
- [ ] Step 3: Validate mapping (run validate_fields.py)
- [ ] Step 4: Fill the form (run fill_form.py)
- [ ] Step 5: Verify output (run verify_output.py)
```

**Step 1: Analyze the form**

Run: `python scripts/analyze_form.py input.pdf`

This extracts form fields and saves to `fields.json`.
```

Benefits: clear progress tracking, prevents skipping steps, easy to resume after interruption.

## Anti-Patterns

**Vague descriptions:**
- `description: Helps with documents` ✗
- `description: Extract text and tables from PDF files. Use when working with PDF files or when the user mentions PDFs.` ✓

**First/second person in description:**
- `description: I can help you process Excel files` ✗
- `description: Processes Excel files and generates reports` ✓

**Directory name doesn't match skill name:**
- Directory `facebook-ads`, name `facebook-ads-manager` ✗
- Directory `manage-facebook-ads`, name `manage-facebook-ads` ✓

**XML tags in skill body:**
- Using `<objective>`, `<quick_start>`, `<workflow>` tags ✗
- Using `## Quick Start`, `## Instructions`, `## Workflow` headings ✓

**Too many options (decision paralysis):**
- Listing 6 library alternatives without a recommendation ✗
- Recommending one default with a single escape hatch ✓

**Deeply nested references:**
- `SKILL.md → advanced.md → details.md` ✗
- `SKILL.md → advanced.md`, `SKILL.md → details.md` ✓

**Windows paths:**
- `scripts\helper.py` ✗
- `scripts/helper.py` ✓

**Side-effect skill without `disable-model-invocation: true`:**
- Deploy, commit, or send skills that Claude can trigger automatically ✗
- Same skills with `disable-model-invocation: true` so only you trigger them ✓

**Shell injection in documentation without escaping:**
- Writing `` !`git status` `` in skill content when you mean it as an example ✗
- Writing `` ! `git status` `` (with a space) to show it as documentation ✓
