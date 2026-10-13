# Common Patterns

Common patterns for skill authoring: templates, examples, terminology, and new features.

## Template Pattern

Provide output templates for consistent results. Match strictness to the task.

**Strict** — when output format must be exact:

````markdown
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
````

**Flexible** — when the agent should adapt based on context:

````markdown
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
````

Use strict when: compliance reports, standardized formats, automated processing.
Use flexible when: exploratory analysis, context-dependent formatting, creative tasks.

## Examples Pattern

For skills where output quality depends on seeing examples, provide input/output pairs.

````markdown
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
````

Use examples when:
- Output format has nuances that text explanations can't capture
- Pattern recognition is easier than rule following
- Examples demonstrate edge cases
- Multi-shot learning improves quality


## Live Context Pattern

Gather dynamic context using explicit tool steps rather than load-time command injection:

```markdown
---
name: summarizing-prs
description: Summarizes a pull request and highlights review risks. Use when preparing a PR summary or reviewing changes.
---

# Summarizing PRs

1. Identify the repository and pull request from the user's message.
2. Fetch its description, diff, and changed files using available tools.
3. Inspect relevant surrounding code.
4. Summarize what changed, why, and what a reviewer should check.
```

## Invocation Control Pattern

Automatically discoverable skills need only `name` and `description` plus instructions. Choose explicit-only when the user wants to control the workflow's timing.


For an explicit-only native skill:

```markdown
---
name: deploying-preview
description: Deploys the current project to a preview environment. Invoke when ready to publish a preview.
disable-model-invocation: true
---

# Deploying Preview

Confirm the target from the user's message, run tests, deploy using available tools and approvals, and verify the preview URL.
```

Invoke with `/deploying-preview`. Plugin-qualified slash commands are valid too. Use `user-invocable: false` only for intentionally background-only skills; omit invocation restrictions for normal automatic-and-explicit use.


## User Input Pattern

```markdown
## Inputs

Read the component, source framework, and target framework from the user's message.
Ask for any missing value before making changes.

## Instructions

Migrate the named component between the confirmed frameworks.
Preserve existing behavior and run relevant tests.
```

Do not assume Claude argument substitutions, shell injection, or tool preapprovals. Resolve scripts from the discovered skill directory and execute them through the available shell tool. See [invocation-and-arguments.md](invocation-and-arguments.md) for complete examples.


## Consistent Terminology

Choose one term and use it throughout. Inconsistent terminology confuses the agent and reduces quality.

**Good** — consistent usage:
- Always "API endpoint" (not mixing with "URL", "API route", "path")
- Always "field" (not mixing with "box", "element", "control")
- Always "extract" (not mixing with "pull", "get", "retrieve")

**Bad** — inconsistent usage creates confusion:
- Mix "API routes", "URLs", "paths", "endpoints" — are these the same?
- Mix "fields", "boxes", "elements", "controls" — the agent must guess

Implementation:
1. Choose terminology early in skill development
2. Document key terms in a `## Glossary` section if domain is specialized
3. Use find/replace to enforce consistency across all files

## Default with Escape Hatch

Provide one default approach with a single escape hatch for edge cases. Avoid offering many alternatives upfront — it creates decision paralysis.

**Good:**

````markdown
## Quick Start

Use pdfplumber for text extraction:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```

For scanned PDFs requiring OCR, use pdf2image with pytesseract instead.
````

**Bad** — too many options:

```markdown
## Quick Start

You can use any of these libraries:
- **pypdf**: Good for basic extraction
- **pdfplumber**: Better for tables
- **PyMuPDF**: Faster but more complex
- **pdf2image**: For scanned documents
```

The agent must now research and compare all options before starting.

## Progressive Disclosure Pattern

Keep `SKILL.md` concise by linking to reference files. The agent reads them only when needed.

```markdown
## Advanced Features

**Custom audiences**: See [audiences.md](audiences.md)
**Conversion tracking**: See [conversions.md](conversions.md)
**Budget optimization**: See [budgets.md](budgets.md)
**API reference**: See [api-reference.md](api-reference.md)
```

Benefits: `SKILL.md` stays under 500 lines, the agent only reads relevant references, token usage scales with task complexity.

## Validation Pattern

For skills with validation steps, make validation scripts verbose and specific.

````markdown
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
````

## Checklist Pattern

For complex multi-step workflows, provide a checklist the agent can copy and track.

````markdown
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
````

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


**Invocation policy mismatches:**
- An output intended to be explicit-only still auto-loads ✗
- An output intended for discovery is restricted only because its authoring tool is explicit-only ✗
- The selected mode uses the active client's supported control mechanism ✓

**Source/native confusion:**
- Copying canonical `targets`, tool declarations, or Jinja into a native `SKILL.md` ✗
- Writing native metadata and ordinary prompt input/tool steps ✓
