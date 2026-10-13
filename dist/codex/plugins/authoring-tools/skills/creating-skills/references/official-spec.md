# Native Skill Specification

This reference describes native output for the active client. For scope selection, safe edits, and the separate opt-in marketplace-source format, read [authoring-targets.md](authoring-targets.md).

Use an unprefixed `name` matching the folder, at most 64 lowercase letters, numbers, and hyphens. Use a non-empty `description` of at most 1,024 characters. These examples are native files, not canonical marketplace YAML.



## Codex

Source: [Codex Agent Skills](https://developers.openai.com/codex/skills/)


## What Is a Skill

A skill is a directory containing `SKILL.md`: YAML metadata between `---` markers followed by Markdown instructions. The client discovers the name and description first, then loads instructions and linked resources when relevant.

```markdown
---
name: processing-pdfs
description: Extracts text and tables from PDF files. Use when working with PDFs or document extraction.
---

# Processing PDFs

## Quick Start

Identify the input file and requested output from the user's message. Ask for missing details.

## Instructions

1. Check the input and required dependencies.
2. Resolve any bundled script relative to this SKILL.md.
3. Run extraction with the available shell tool.
4. Verify the output and report its location.

## Additional Resources

Read references/forms.md only when working with PDF forms.
```

Create any resource actually referenced by an output skill, or remove the link.

## Skill Locations


| Scope | Path |
|-------|------|
| Workspace | `.agents/skills/<skill-name>/SKILL.md` |
| Personal | `~/.agents/skills/<skill-name>/SKILL.md` |
| Existing plugin | `<plugin>/skills/<skill-name>/SKILL.md` |

Use `$skill-name` for explicit invocation. Keep `$` and plugin prefixes out of the YAML name. Do not create a second copy when a selected skill already exists.


## Supported Authoring Metadata

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unprefixed folder name; lowercase letters, numbers, hyphens; at most 64 characters. |
| `description` | Yes | What it does and when to use it; non-empty, at most 1,024 characters. |

Use `name` and `description` in `SKILL.md`. Optional Codex interface and invocation configuration belongs in **`agents/openai.yaml`**, not in the skill's main YAML.

### Explicit-Only Native Example

`SKILL.md`:

```markdown
---
name: deploying-preview
description: Deploys the current project to a preview environment. Use when ready to publish a preview.
---

# Deploying Preview

Read the target environment from the user's message. Confirm the target, run tests, request any required tool approval, deploy, and verify the preview URL.
```

`agents/openai.yaml`:

```yaml
policy:
  allow_implicit_invocation: false
```

Invoke with `$deploying-preview`. To allow automatic discovery, omit this policy or set `allow_implicit_invocation: true`. Do not add `disable-model-invocation` or `user-invocable` to Codex `SKILL.md`. Preserve any existing interface configuration when editing this policy.


## Inputs and Tool Execution

Task inputs come from the user's ordinary prompt. Ask for missing values; do not interpret `$ARGUMENTS`, positional substitutions, or named-argument declarations as client features.

Gather dynamic context in explicit steps using available tools, for example:

1. Run `git branch --show-current`.
2. Read the requested diff with `git diff` or the available GitHub tooling.
3. Summarize the observed result, distinguishing facts from assumptions.

Do not copy Claude shell injection, `allowed-tools` preapproval, `context: fork`, agent/model overrides, or lifecycle hooks into native skill metadata. Skills do not bypass normal approvals or guarantee subagent support.

Resolve bundled resources relative to the discovered skill directory. Assign an ordinary `SKILL_DIR` variable to that absolute location before using a command such as `python "$SKILL_DIR/scripts/analyze.py" input.pdf`. Check dependencies first; keep project input paths relative to the intended working directory.

## Progressive Disclosure and Verification

Keep `SKILL.md` under 500 lines as an authoring guideline, not a parser limit. Link detailed workflows, references, templates, and scripts directly from it with clear loading instructions. Do not load the full library for every task.

Verify YAML syntax, metadata lengths, folder/name agreement, resource links, and invocation policy. Test a matching prompt and an unrelated prompt for automatic skills; test explicit invocation and absence of automatic loading for explicit-only skills. Confirm discovery in the active client and reload or restart if necessary rather than assuming another client's live-update behavior.
