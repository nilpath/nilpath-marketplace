# Plan checker

[Script](../scripts/check_plan.py). Validate the checklist produced by
[Multi-phase plan](../playbooks/multi-phase-plan.md) without executing it.
Requires Python 3.11+, with no external Python packages.

## Run

Resolve the script from the installed nstack-flow directory. Keep the project
working directory.

```bash
python3 "<nstack-flow skill directory>/scripts/check_plan.py" <plan.md>
```

The first argument is the plan path; additional arguments are ignored. This
checker does not have a `--help` option. It reads the plan without modifying it.

## Checks and results

The checker validates lexical Markdown structure, not the meaning of the plan.
It checks heading and sub-block order, evidence checkboxes, ten live lanes,
performance items, review-gate fields, the rendered audit-cadence marker and
selected prose rules. Fenced examples are excluded from structural checks;
literal marker searches still inspect raw section bodies.

Stdout contains each PR's checkbox counts and a final problem count. Stderr
contains accumulated `<file>:<line>: <problem>` diagnostics.

| Exit | Meaning |
| --- | --- |
| 0 | No validation problems |
| 1 | Validation problems found |
| 2 | Missing plan path |

File-read and unexpected runtime failures remain errors rather than validation
results. Fix the reported problems and rerun before handing back the plan.
A passing result does not execute verification, prove dependency correctness
or authorize implementation.
