# Invocation Control and Inputs

Choose the output skill's invocation mode with the user. This authoring skill is explicit-only, but the skills it creates may be automatically discoverable. Scope and placement are resolved separately in [authoring-targets.md](authoring-targets.md).


## Invocation Modes


| Configuration | Explicit invocation | Automatic loading |
|---------------|---------------------|-------------------|
| Default policy | Yes | Yes |
| `policy.allow_implicit_invocation: false` in `agents/openai.yaml` | Yes | No |

Invoke with `$skill-name`; for this authoring skill use `$creating-skills`. Do not place the `$` or a plugin prefix in YAML.

An explicit-only output still has ordinary `SKILL.md` metadata:

```markdown
---
name: deploying-preview
description: Deploys a tested project to a preview environment. Use when ready to publish a preview.
---

# Deploying Preview

1. Read the target from the user's message; ask if it is missing.
2. Confirm deployment scope and run the project's tests.
3. Resolve scripts/deploy.sh relative to this skill directory.
4. Run it with the confirmed target through the shell tool and normal approvals.
5. Verify the preview URL and report the result.
```

Add this separate file at `agents/openai.yaml`:

```yaml
policy:
  allow_implicit_invocation: false
```

Do not add `disable-model-invocation`, `user-invocable`, or policy keys to main skill YAML. For automatically discoverable output, omit the policy or use `true`. Preserve existing interface metadata when updating the policy.


## Ordinary Prompt Inputs

Describe expected inputs in the Markdown instructions:

```markdown
## Inputs

Read the issue number and repository from the user's message. If either is unclear, ask before fetching or changing anything.

## Instructions

1. Fetch the identified issue using available tooling.
2. Understand its acceptance criteria.
3. Implement the requested fix.
4. Run relevant tests.
5. Report the changes and verification results.
```


Example request: `$fix-issue Fix issue 123 in owner/repo and run the relevant tests.`


Do not rely on Claude `$ARGUMENTS`, `$0`, named argument substitution, or session variables. A shell script may accept arguments normally after the agent has resolved and validated the user's inputs.

## Dynamic Context Through Explicit Tool Steps

Instead of load-time shell injection, instruct the agent to gather current state:

```markdown
## Pull Request Summary

1. Identify the repository and requested pull request.
2. Run `gh pr view` and `gh pr diff` for that pull request, or use available equivalent tools.
3. Read relevant files if the diff alone is insufficient.
4. Summarize what changed, why, and remaining risks.
```

Tool results are observed during execution. There is no assumed pre-render command execution or tool preapproval. Do not include `context: fork` or a Claude `agent` field; if delegation is requested and supported, describe it using the client's available mechanism.

## Bundled Resource Execution

Resolve `scripts/`, `references/`, and `templates/` against the selected skill root. `SKILL_DIR` in examples is an explicitly assigned shell variable, not client interpolation:

```bash
SKILL_DIR="/absolute/confirmed/path/to/deploying-preview"
bash "$SKILL_DIR/scripts/deploy.sh" preview
```

Keep the project working directory unchanged when the script operates on project files. Quote paths, check prerequisites, honor approvals, and verify output before claiming success.

## Test Both Invocation Paths

- Automatic skills: a relevant prompt should load the skill; unrelated prompts should not.
- Explicit-only skills: explicit invocation should work; relevant ordinary prompts should not auto-load it.
- Verify missing inputs lead to clarification, not invented values.
- Confirm the expected workflow and resources are used from the selected directory.
