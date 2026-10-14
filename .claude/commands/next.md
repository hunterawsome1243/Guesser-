---
description: Do the next task from PLAN.md
argument-hint: [optional note about the task]
disable-model-invocation: true
---

Read CLAUDE.md and PLAN.md, then pick one thing to work on: the first unchecked blocker under "Bugs to fix" if there is one, otherwise the first unchecked task ("- [ ]") under a Milestone heading, in the first milestone that still has one.
Extra note from me, if any: $ARGUMENTS

1. Tell me what you picked. If it is a task with indented "- [ ]" steps under it, work on its first unchecked step. Unless it is marked (S), give me your plan in a few bullets and wait for my OK before you edit anything. If it is marked (L) and has no steps yet, tell me how you would split it into steps, wait for my OK, write them as indented "- [ ]" lines under it, then do only the first one.
2. Make the change in small steps, touching only what it needs. For a bug, find the cause before changing code (reproduce it if you can), and if the project has tests, add one that fails because of the bug.
3. Run the test or build command from the Commands section of CLAUDE.md and fix any failures. A check that is not set up yet (a later task adds it) is not a failure: say so. If this project has a reviewer subagent (.claude/agents/reviewer.md), ask it to check the change and fix what it finds.
4. When it works, change its "- [ ]" to "- [x]" in PLAN.md, and for a task add today's date to its brackets: "(S)" becomes "(S, done YYYY-MM-DD)". For a step under a large task, tick the step, and tick the task itself only when all its steps are ticked. Put anything worth remembering on a short indented "Notes:" line under it, and add any extra work you found as a new "- [ ]" line at the end of its milestone. Do not reorder, rename or delete other lines.
5. Finish with a short summary: what changed, what I should test by hand, and anything left over. End with two lines for my log: "Outcome: done" (or "partly done", or "stuck"), then "Went wrong:" and what went wrong, or "nothing". Put nothing after them.
