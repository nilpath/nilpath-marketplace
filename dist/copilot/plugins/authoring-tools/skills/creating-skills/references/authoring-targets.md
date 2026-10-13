# Authoring Target and Placement

## Native Output Is the Default

Unless the user explicitly requests marketplace sources, create a native `SKILL.md` for the active client. Supporting Markdown and scripts are ordinary files. Do not introduce `targets`, canonical tool declarations, Jinja, or generated `dist/` paths into native output.

Use a direct chat question to the user (wait for their reply before continuing) to resolve unspecified **workspace versus personal** scope before creating anything. Do not assume a personal location just because earlier examples used one. If the user supplies a path, confirm that it is discoverable by the intended client and that its folder matches the skill name.


| Scope | Native location |
|-------|-----------------|
| Workspace | `.github/skills/<skill-name>/SKILL.md` or `.agents/skills/<skill-name>/SKILL.md` |
| Personal | `~/.copilot/skills/<skill-name>/SKILL.md` or `~/.agents/skills/<skill-name>/SKILL.md` |
| Existing plugin | `<plugin>/skills/<skill-name>/SKILL.md` |

Prefer the existing project convention. If none exists, propose `.github/skills` for workspace scope or `~/.copilot/skills` for personal scope; confirm the choice. Use `.agents/skills` when that is the user's shared convention. Never create copies in both locations. Invoke local skills with `/skill-name`; plugin invocation such as `/authoring-tools:creating-skills` is valid.


Creating a skill in a plugin is appropriate only when the user has selected that plugin as the destination. Do not create plugin manifests or duplicate installed marketplace content merely to make a local skill.

## Resolve Once, Reuse Throughout

1. Establish the active client, output mode, scope, skill name, and invocation mode.
2. Inspect existing discovery directories within the selected scope. If multiple candidates share a name, show their full paths and let the user select one.
3. Record the exact destination as `SKILL_DIR`. In shell examples this is an ordinary variable explicitly assigned to that resolved directory, not a built-in client variable.
4. Check for existing files and ask before replacing them. For audit/verify/edit tasks, work on the selected skill in place; do not relocate it or create another copy.
5. Use the chosen directory for every workflow, reference, template, script, and invocation-policy file.

Example after the user has confirmed a path:

```bash
SKILL_DIR="/absolute/confirmed/discovery-root/processing-pdfs"
mkdir -p "$SKILL_DIR"
```

Replace the example path with the actual approved path before running it. Re-establish the variable in each new shell invocation when necessary.

Resolve resource paths from `SKILL.md` and quote paths in shell commands. Preserve the user's project working directory when executing scripts that operate on project files. Relative input/output paths should refer to the project, not accidentally to the installed skill folder. Scripts use normal tool approvals; a skill is not a permission bypass.

Native templates are [simple-skill.md](../templates/simple-skill.md) and [router-skill.md](../templates/router-skill.md). Their default is automatically discoverable. For explicit-only outputs, follow [invocation-and-arguments.md](invocation-and-arguments.md); do not copy this authoring skill's own policy indiscriminately.

## Opt-In Marketplace Source Mode

Only use this mode when the user requests authoring in this marketplace's `src/` tree. Confirm the plugin, intended targets, and component name. Sources belong under `src/plugins/<plugin>/skills/<name>/`; never edit generated `dist/` or root registries by hand.

The following is a **marketplace `SKILL.md.j2` source example, not a native `SKILL.md`**:


```jinja
---
name: inspecting-changes
description: Inspects local changes and summarizes their impact. Use when reviewing an uncommitted diff.
targets: [claude, copilot, codex]
tools: [file-read, content-search, shell(git:*)]
---

# Inspecting Changes

Read the diff and summarize the impact. Track substantial work with {{ todo }}.
Resolve unclear scope using {{ ask_user }}.
```


Source `targets` and canonical tools are transformed by the builder; they are not literal native fields. Canonical names come from `src/harnesses/tools.yaml`, not from a client-specific tool list. Use the existing prose helpers for orchestration phrasing.

Supporting `.j2` files render **text only**: the builder removes the `.j2` suffix and does not transform their YAML. Put native examples inside client conditionals when needed. Empty rendered files are omitted. The builder has no template loader; do not use Jinja `include` or `extends`.

For explicit-only marketplace skills, guard `disable-model-invocation: true` for Claude/Copilot in the entrypoint and add a Codex-only `agents/openai.yaml.j2`:


```jinja
{% if harness == "codex" -%}
policy:
  allow_implicit_invocation: false
{% endif -%}
```


Automatically discoverable marketplace skills should omit those restrictions unless explicitly requested. Guard literal Jinja examples in templated references with raw blocks so examples survive rendering.

Build and validate with the repository's existing workflow when authorized. Inspect each requested client's rendered `SKILL.md`, supporting files, and policy, not just the source. A rendered native file must contain no source-only `targets`, canonical tool declarations, or unresolved Jinja. Preserve existing useful content during any conversion.
