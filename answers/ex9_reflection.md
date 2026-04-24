# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my Ex7 run (session sess_a382a2149fc1), the planner's second
subgoal was sg_2 "commit the booking under policy rules" with
assigned_half: "structured". The signal that drove this was the task
text naming a deterministic constraint — "under policy rules".
Sovereign-agent's DefaultPlanner is prompted with the list of
available halves and their purposes; when subgoal description
mentions rules/policy/limits, the planner prefers structured.

This decision is advisory, not physical. The orchestrator respects
it only because both halves are wired up. If only a loop half
existed (as in research_assistant), a subgoal assigned to structured
would go to the void. That's failure mode #4 from the course slides.

The broader lesson: the planner makes an architectural decision
based on prose interpretation. Put the rules somewhere the LLM
cannot mis-assign — in the structured half's Python — and prose
ambiguity no longer matters.

### Citation

- sessions/sess_a382a2149fc1/logs/tickets/tk_*/raw_output.json
- sessions/sess_a382a2149fc1/logs/trace.jsonl:23

---

## Q2 — Dataflow integrity catch

### Your answer

During Ex5 development my integrity check caught a subtle fabrication
that manual review missed. In session sess_de44a1b8eb12 the flyer
claimed "Total: £560" and "Deposit: £112" — plausible numbers that
followed the deposit formula in catering.json. I skimmed and moved on.

verify_dataflow returned ok=False with unverified_facts=['£560','£112'].
The trace showed calculate_cost returned total_gbp=540, deposit=0. The
real total was £540 under the £300 deposit threshold. The LLM had
written "£560" plausibly — close enough that a human reviewer wouldn't
notice without cross-referencing.

The check caught it because it compared against ground truth in
_TOOL_CALL_LOG, not against "does this look reasonable." The lesson
generalises: if the validator would pass a human skim, plant a
deliberately-weird value like £9999 and confirm it's caught.

### Citation

- sessions/sess_de44a1b8eb12/workspace/flyer.md:12
- sessions/sess_de44a1b8eb12/logs/trace.jsonl:15

---

## Q3 — Removing one framework primitive

### Your answer

I'd keep session directories (Decision 1) as the last thing standing
and rebuild everything else if forced. The forward-only state machine
(Decision 2) is important but fragile without directories. Tickets
(Decision 3) I could rebuild as .jsonl files inside the session.
Atomic-rename IPC (Decision 5) is replaceable by directory polling.

Session directories are the irreplaceable piece. Losing them:
cross-tenant data leaks, reconstructing per-run state from logs,
"how did this session end up this way" becomes SQL archaeology
instead of cat. The slides compare it to git commits being the
foundation — you can rebuild merge, diff, blame from commits but
not commits from the rest. Session directories are commits.

### Citation

- sessions/sess_de44a1b8eb12/ — the directory itself
- sessions/sess_a382a2149fc1/logs/trace.jsonl
