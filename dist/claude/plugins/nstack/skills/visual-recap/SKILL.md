---
name: visual-recap
description: Explain actual code changes in a rich local MDX review document with evidence, diagrams, annotated code, before-and-after comparisons, UI states, and API contract changes. Use for a visual change recap, implementation walkthrough, or review handoff.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Visual recap

Explain what actually changed and what remains uncertain. MDX is the source. The shared local viewer renders the recap. Do not turn a proposal into an implementation claim or replace the document with a Markdown wall.

Read [the shared viewer workflow](../visual-plan/references/viewer.md) first. Both visual skills use the same viewer, components, publication commands, and durable feedback.

## 1. Establish the evidence

Identify the change being recapped. Read the relevant diff and changed code. Include staged and unstaged changes when they belong to the request. State the base, head, worktree scope, and any excluded files in the document.

Use a user-supplied comparison base when given. Otherwise inspect the branch and its upstream before selecting a merge base. Do not guess that `HEAD~1` represents the feature or that the local default branch is current.

Reuse a visual plan, architect output, or show-me-your-work trail if present. Check its claims against the actual code. Do not build a second decision log or assume the approved plan exactly matches the implementation.

Collect file and line references, commit IDs, command results, and existing verification artifacts. Running a command is evidence of its output only. A static test is not proof of browser behavior or runtime hook execution.

## 2. Compose the MDX

Write a `.mdx` artifact in the current session's artifact directory, or the user's requested repository location. Keep its absolute path. Use a stable project-specific ID separate from the plan, such as `checkout-retry-recap`.

When revisiting this recap in another session, reuse its original canonical MDX path. Do not copy it into a new artifact directory under the same ID. Use a stable user-selected repository path for a review that must outlive session artifacts. Source-identity migration is not supported in v1.

Start with a `Document` element whose `kind` is `recap`. Use short prose to explain the consequence for the user and the next maintainer.

Choose rich blocks that expose the change:

- Use `Diagram` for the implemented flow and `FileMap` for changed ownership.
- Use `AnnotatedCode` and `BeforeAfter` for code that explains the behavior.
- Show implemented UI with `Wireframe` and `StateSequence`. Label schematic wireframes honestly. They are not screenshots.
- Use `ApiContract` for the actual HTTP route or non-HTTP signature. Include authentication, parameters, expandable schemas, and request, response, and error examples.
- Use `ApiComparison` to show the old and new contracts and compatibility implications.
- Use `Decision` to explain a choice supported by the evidence. Use `Question` for unresolved review input, not to manufacture approval.

Read the viewer's component reference and all-components sample before authoring payloads. Use stable unique block IDs, literal attributes, and fenced JSON data. Do not add imports, JavaScript expressions, HTML, credentials, or external embeds.

Label each substantive block honestly. `implemented` requires evidence references. `inferred` requires a reason. `context` marks existing reference material. `proposed` is only for an explicitly unimplemented follow-up. Separate observed behavior from inferred intent.

Include failures, skipped checks, limitations, and deviations from the plan. Never convert a missing test, a mock, or a prediction into a passing result.

## 3. Publish and inspect

Validate and publish through the shared workflow. Fix compiler diagnostics before sharing. Open the same document URL in an ordinary browser or optional app Browser canvas.

Inspect the rendered code, diagrams, API schemas, comparisons, and status labels. Exercise state-sequence controls and review questions when available. Read persisted feedback before revising the recap. Changed questions make old answers stale.

Do not mutate code or execute an API request merely to make the recap appear complete. Report missing or contradictory evidence.

## 4. Hand back the document

Return the browser link, canonical MDX path, the main observed change, and unverified claims or outstanding review questions. Keep the chat response short. The evidence and explanation belong in the rendered recap.
