# Shared visual viewer workflow

The `visual-plan` and `visual-recap` skills use one viewer and one component vocabulary. The source is MDX. Published data and feedback live outside the installed plugin.

## Resolve the viewer

Resolve `<viewer>` to an absolute path without changing the repository working directory:

`../../hooks/viewer/viewer.mjs` from the base directory of either visual skill.

If this reference file is the only available location, first resolve its parent skill directory. Relative paths above start from that directory, not `references/` or the checkout.

Node.js 20 or newer must be on `PATH`. V1 viewer hosting requires macOS or Linux. Native Windows users need WSL or another Linux host because the private state directory uses POSIX permissions. Runtime commands need ordinary tool approval. This skill does not grant blanket interpreter permissions.

The session-start hook starts or reconnects to the viewer and adds ready or warning context. When hooks are unavailable, untrusted, disabled, or failed, run the same fallback:

```bash
node "<viewer>" ensure
```

Read the returned JSON. Only `ok: true` with a verified URL means ready. On a nonzero exit or `ok: false`, show the error and its repair. Do not report a successful start or silently switch to hosted rendering.

## Read the component contract

Run:

```bash
node "<viewer>" components
```

Read the `all-components.mdx` sample beside `<viewer>`. The runtime registry and sample define literal attributes and component payloads. Do not guess a schema from a component's name.

MDX permits headings, prose, lists, safe links, code fences, and the allowlisted components. Each rich component has literal attributes and a fenced JSON payload. The compiler parses MDX with an established AST parser. It does not evaluate document JavaScript.

For plans, use `proposed` for changes and `context` for existing reference material. For recaps, `implemented` needs evidence and `inferred` needs a reason. A recap may label an unimplemented follow-up `proposed`. These labels describe the author's evidence, not independent proof by the viewer.

## Validate and publish

Keep the `.mdx` file as the canonical artifact. Use a stable document ID and stable block IDs. Do not reuse one ID for unrelated projects, or for both a plan and its recap.

```bash
node "<viewer>" check "/absolute/path/review.mdx"
node "<viewer>" open "/absolute/path/review.mdx"
```

`check` validates without starting the viewer. `open` compiles, publishes, and ensures the same viewer is running. Inspect its JSON result and open the exact `url`, including its local access capability. The ready origin from `ensure` is not a document link. Do not invent a port, remove URL parameters, or construct a URL from a PID.

The viewer serves only published documents and fixed assets. File names, code, API targets, schema references, and evidence references are display data, not commands to read files or make network requests. API contracts are read-only.

## Open the document

Use an available browser-opening tool or give the returned link to the user. Claude Code, Copilot CLI, and Codex can all use an ordinary local browser. A remote agent's loopback address belongs to the remote host and needs a private forwarded port or tunnel to reach the user's browser. Do not expose the viewer on a public interface.

In the Copilot app, if the `browser` canvas is listed, inspect its capabilities and open the returned URL with its `{url, title}` input. Reuse the same URL rather than forking the document into canvas-specific state. Native Copilot inside VS Code is unsupported. No app SDK extension or canvas dependency is required.

Treat the access URL as private. The viewer exchanges its local capability for a browser cookie and removes the capability from the address bar. Give another browser a fresh link from `open`, not the cleaned address copied from an authenticated tab. Do not post access links to public services or logs.

If browser automation is available, inspect the rich blocks and interact with the document. A successful build or HTTP response is not proof of correct rendering. State what you could not inspect.

## Read feedback and update

```bash
node "<viewer>" answers "<document-id>"
```

Read this result after the user reviews questions. Answers are stored by document and stable block ID, not by browser tab or canvas instance. They survive reload and server restart. Changed question content makes an old answer stale. Do not silently carry it forward as the user's current decision.

Publish updates from the same canonical source path, including across sessions. If the viewer reports an ID collision, choose a new project-specific ID or return to the original source. Do not overwrite another document or hand-edit stored identity to repair it. V1 has no source-migration command.

## Lifecycle and failures

Mutable state lives under `$NSTACK_HOME/viewer/`, or `~/.nstack/viewer/`. Installed plugin files stay read-only. The viewer binds to loopback and uses a build-specific runtime identity. Concurrent `ensure` calls reuse a healthy matching viewer.

The hook does not install packages. Missing Node, invalid MDX, an unresponsive owner, or failed readiness must produce an explicit warning or error. The model hook remains independent of viewer availability. `NSTACK_VIEWER=off` disables hook startup. An explicit `open` or `ensure` remains the fallback. Reading saved feedback does not require starting the viewer.

Do not kill processes by name, remove shared runtime directories, or change global client configuration. To stop the matching viewer deliberately, use its identity-checked command:

```bash
node "<viewer>" stop
```

Closing a browser panel does not stop the user-owned viewer. Hook shutdown delivery is not assumed.
