# authoring-tools

Author skills and subagents, and create or maintain project-local verification workflows. The verification workflows support Claude Code, GitHub Copilot, and Codex; the original authoring guides remain Claude-only because they document Claude Code's own formats.

Version: **0.9.0**

## Skills

All four authoring skills require explicit invocation. Claude and Copilot use `disable-model-invocation: true`; Codex uses a skill-local `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.

| Skill | Harnesses | Purpose |
| --- | --- | --- |
| creating-skills | Claude only | Create, write, and refine Claude Code Skills |
| creating-agents | Claude only | Design and implement Claude Code subagents and multi-agent workflows |
| create-verification-skill | Claude, Copilot, Codex | Generate and prove a project-local skill for driving the real app |
| maintain-verification-skill | Claude, Copilot, Codex | Check source and live behavior, maintain the feature map, and ship proven corrections in one PR |

## Invocation

| Skill | Claude / Copilot VS Code plugin command | Codex |
| --- | --- | --- |
| creating-skills | `/authoring-tools:creating-skills` (Claude only) | Not distributed |
| creating-agents | `/authoring-tools:creating-agents` (Claude only) | Not distributed |
| create-verification-skill | `/authoring-tools:create-verification-skill` | `$create-verification-skill` |
| maintain-verification-skill | `/authoring-tools:maintain-verification-skill` | `$maintain-verification-skill` |

For skills copied into a project's skill directory instead of installed through the plugin, use the unqualified skill name, such as `/create-verification-skill` on Claude/Copilot. Copilot CLI shares the Copilot output, but manual-only invocation has known runtime limitations; see the [marketplace's compatibility caveat](https://github.com/nilpath/nilpath-marketplace#manual-only-skills). The manual-only flag is not relaxed for CLI compatibility.

## Verification workflow

Run creation in the application repository. It discovers the app's actual startup command, authentication and seed requirements, driving tools, and evidence sources. It writes only the active harness's project-local verification skill:

| Active harness | Output |
| --- | --- |
| Claude | `.claude/skills/verify-<app>/` |
| Copilot | `.github/skills/verify-<app>/` |
| Codex | `.agents/skills/verify-<app>/` |

The output includes Launch, Doctor, Drive, Evidence, Cleanup, and Helpers instructions plus a feature map, initially aiming for 3-5 features. Creation must run one mapped feature end to end and confirm its evidence survives teardown. It does not certify the whole map. Generated verification skills remain eligible for automatic discovery unless the user requests otherwise.

Maintenance discovers compatible skills across all three locations, deduplicates paths to the same directory, and asks when distinct candidates exist. It maintains the selected directory in place, without creating synchronized copies. Every mapped feature requires source and live coverage, including its documented user entry points. Source reading may use read-only subagents where useful, with a direct-reading fallback; the coordinator alone drives the app.

Maintenance edits only the verification skill and its owned map/harness files. It reports product regressions rather than modifying product code or weakening expected behavior. Evidence survives cleanup, failed attempts are cleaned up, and harness fixes must be re-driven before shipping.

### Shipping and prerequisites

Install **git-tools** alongside this plugin for maintenance's `git-commits` workflow. Shipping also requires Git, an appropriate remote/base branch, and authenticated GitHub CLI (`gh`) access.

- **clean:** complete source/live coverage with no corrections to ship; no new branch or PR.
- **changed:** proven corrections committed, pushed, and included in one confirmed PR.
- **blocked:** incomplete coverage or unsafe/failed shipping; no PR is initiated while blocked. The report identifies the blocker, evidence, and any edits, commit, remote branch, or PR left by a partially successful publishing attempt. Ambiguous publishing responses require a remote-state check, not a blind retry.

Maintenance never stages unrelated work or commits scratch notes and proof artifacts. Generation does not commit or open a PR unless explicitly requested.

## Attribution

The verification workflows and feature-map examples are adapted from [cursor/plugins pstack](https://github.com/cursor/plugins/tree/1b6d44ff26d4e242f4e8f68c391e6d2f7ca16def/pstack), copyright (c) 2026 Lauren Tan, under MIT. The full notice is bundled with both the [creation skill](./skills/create-verification-skill/LICENSE) and [maintenance skill](./skills/maintain-verification-skill/LICENSE).

> Generated from this repo's `src/plugins/authoring-tools/` sources — edit there, not in `dist/`.
