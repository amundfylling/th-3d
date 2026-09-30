# Autonomous batch policy (iterations 06-20)

Authorised by the user on 2026-09-30 ("Let's go", after the condensed /goal text). This file keeps
the policy across context compaction and fresh sessions. Read it together with `docs/state.md`.

## Goal

Complete every remaining iteration through **20** in `Claude_Code_Stiga_Iteration_Prompts.md`, in order,
each with demonstrated verification. Otherwise stop with a documented genuine blocker, or after
**3 failed repair cycles** on one iteration. Stop after iteration 20: no motion reconstruction and no
animated shots.

## Authorisation

- Run consecutive iterations without asking for approval of each one. This overrides the routine
  "do one iteration and stop" wording in CLAUDE.md and the prompts, for this batch only.
- Do the intermediate visual reviews myself and label them **AI review**. Never claim the user's
  personal approval.
- Keep all other project constraints (CLAUDE.md working rules 2-10).

## Per iteration

1. Read its full prompt and prerequisites.
2. Before implementing, write a short acceptance checklist in `docs/state.md` under "Active
   iteration". It separates code correctness, visual fidelity and physical evidence.
3. Implement only that iteration's scope.
4. Run the applicable type checks, validation, builds and meaningful tests.
5. For visual work, generate the required overlays, screenshots or renders and actually inspect them
   against the reference images. A successful render does not prove visual correctness.
6. Review against the checklist and name concrete defects.
7. On a failed check, fix the cause and rerun the affected checks. At most 3 repair cycles per
   iteration, counted persistently in `docs/state.md` (repair count).
8. Advance only when every applicable criterion has passed with recorded evidence.
9. Update `docs/state.md` with the outputs, the checks actually run, the visual findings and the
   remaining uncertainty. Commit the iteration, push to the working branch, then start the next.

## Verification rules

- Never delete or weaken a check, relax a tolerance or change an acceptance criterion just to pass.
  Fix a demonstrably wrong check only with a recorded explanation.
- Never report a check or inspection that was not performed. Required checks that cannot run are
  blockers, not passes.
- Use the canonical geometry and preserve the reference originals. Keep rigid figure mechanics,
  independent travel and rotation, handedness, goalie differences and contact geometry consistent.
- Keep measured, catalog_nominal, traced, assumed and unknown distinct. Continue with provisional
  geometry only where the iteration allows it. Never claim exact dimensions or verified mechanisms
  without evidence.

## Blockers

- Try reasonable fixes for missing tools through permitted installation methods. Blender: try to get
  a working install (the PyPI `bpy` module) before declaring rendering stages blocked.
- Blocked optional reference downloads are not blockers when the PDF-extracted assets suffice.
- Stop for: missing required physical measurements, a required recording, unavailable essential
  tooling, an unresolved ambiguity that materially changes the result, or exhausted repairs. Never
  invent evidence, skip an iteration or substitute an easier task.

## Finish report

List the completed iterations, verification evidence, review artifacts, unresolved accuracy limits
and the exact input needed next. Label a blocked run **blocked**, never complete.

## Outcome

Completed 2026-09-30: iterations 06-20 done with recorded verification (docs/state.md). Stopped after 20. No iteration hit 3 unsuccessful repair cycles.
