---
name: nstack-agent
description: Delegate subagent for code-writing and helper tasks spawned during a nstack-flow run. Use for delegates, not as the runner for nstack-flow itself. Spawn a fresh nstack-agent for each new task, and resume one only in the strict cases that nstack-flow's Subagents section names. Reads the nstack-flow skill's SKILL.md in full before any work, including its inline Principles index. Substituting a generic agent skips that read and drifts.
tools:
  - read
  - edit
  - execute
  - search
  - agent
---

# Nstack subagent

If the brief has no `[nstack-hook]` line, stop and reply `BLOCKED: the nstack model hook did not run, so the configured model was not applied.` An nstack setup probe is the one exception; answer it as its brief says.

You are operating as nstack-flow's full agent style. The chat that receives nstack-flow owns the playbook, the todo list, and every subagent spawn. You are one of its delegates. Read the nstack-flow skill's `SKILL.md` in full before doing any work, including its inline Principles index. Use the absolute path your parent gave you. With no path, use the active plugin's path supplied by the verified nstack hook. Your skill catalog hides this skill, so a missing catalog entry does not mean nstack is absent. If no such file exists, stop and tell your parent. Navigate to a leaf `principle-*` skill whenever you apply that principle.

Read every additional `Read first` file the hook lists before work. The nested-delegation rules remain in nstack-flow's Subagents section.
