# Documentation Type Reference

Use this table to determine the right structure, tone, and required sections for each documentation type.

## Type Reference

| Type | File pattern | Required sections | Tone | Audience |
|------|-------------|-------------------|------|----------|
| README | `README.md` | Overview, Quick Start, Usage, Configuration, Contributing | Welcoming, concise | Developer |
| API reference | `docs/api/*.md` | Endpoint/function, Parameters, Return value / Response, Examples, Error codes | Precise, example-heavy | Developer |
| Architecture | `docs/architecture.md` | Context & Problem, Design Decisions, Component Overview, Data Flow, Trade-offs | Analytical | Developer / Admin |
| Changelog | `CHANGELOG.md` | Added, Changed, Fixed, Removed (Keep a Changelog format) | Terse, past-tense | Developer |
| Guide / Howto | `docs/guides/*.md` | Goal, Prerequisites, Steps (numbered), Verification, Troubleshooting | Tutorial, step-by-step | End-user / Developer |
| Inline docstring | source files | What it does (one line), Parameters, Return value, Raises / throws | Minimal | Developer |
| Config reference | `docs/config.md` | Key name, Type, Default, Valid values, Description | Precise, tabular | Admin |
| CLI reference | `docs/cli.md` | Command, Flags/Options, Arguments, Examples | Precise, example-heavy | Developer / Admin |

## Style Rules Per Type

### README
- First sentence is a one-line description of what the project does.
- Quick Start must be runnable in under 5 minutes.
- Usage section shows the most common case, not every edge case.
- Do not repeat information that belongs in a separate reference doc — link to it instead.

### API Reference
- Every parameter documented: name, type, required/optional, default (if optional), description.
- At least one code example per endpoint or function.
- Error codes listed with their meaning and common cause.
- Keep prose minimal — developers scan, not read.

### Changelog
- Format: `## [version] - YYYY-MM-DD`
- Use past tense: "Added", "Fixed", "Changed", "Removed" (not "Adds", "Fixes").
- One line per change. Link to PR or issue if available.
- Do not document internal refactors unless they affect the public API.

### Guide / Howto
- State the goal and who this guide is for in the first paragraph.
- List prerequisites before step 1.
- Number every action step. Use bullet points only for non-sequential items.
- End with a verification step ("You should now see…").
- Include a Troubleshooting section for the 2–3 most common problems.

### Docstrings
- First line: imperative mood verb phrase ("Returns the user by ID", not "This function returns…").
- Document all parameters; omit self/this.
- Document what is raised/thrown, not just what is returned.
- Keep it short — if the docstring is longer than the function, the function needs refactoring.
