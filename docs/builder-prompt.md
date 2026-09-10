# Builder prompts

How to hand a task to the building agent. One task per prompt — never a batch.

The template is below; the worked example for **T1** follows it and is ready to
paste as-is.

---

## Template

```
Repository: synclairebarrettllc/GBL-Backend-Rebuild

Read AGENTS.md first. You are on Job A: building the new backend.

TASK: <Tn> — <title>
Its full definition is in docs/spec/24_build-tasks.md. Read that task, and only
that task. Do not start the next one.

LOAD THESE, and nothing else unless the task's `Spec.` line names it:
  docs/spec/20_decisions.md     <- every policy value. Never work without it
  docs/spec/22_traceability.md  <- why each rule exists. Never work without it
  <the phase feed for this task, from 24_build-tasks.md "Context feed">

RULES
- Work on a branch. Never commit to main. One task = one branch = one PR.
- Build what 20_decisions.md says. If you need a value it does not contain,
  stop and say so. Do not choose one.
- Migrations apply before the code that reads them.
- Done means evidence: the command you ran and its output, asserting the
  resulting state. Not "it ran without errors".
- Three failed fix/verify cycles on one thing, then stop and report with a
  root-cause hypothesis. Do not guess a fourth time.

REPORT BACK
- The task's "Done when" criteria, each with the output that proves it
- What you changed, and why, if you departed from the task as written
- Anything in the specification that was wrong, ambiguous, or missing
```

---

## T1 — ready to paste

```
Repository: synclairebarrettllc/GBL-Backend-Rebuild

Read AGENTS.md first. You are on Job A: building the new backend. This repo
currently contains only the specification — no application code, no CI, no
scripts. You are building the first rail.

TASK: T1 — Stand up CI
Full definition in docs/spec/24_build-tasks.md. Read that task only.

LOAD:
  docs/spec/24_build-tasks.md   (Stage 0 section)
  docs/spec/17_operations.md    (§2 migration ordering, §3 the gate chain)
  docs/spec/18_testing.md       (§1 what counts as evidence)
  docs/spec/20_decisions.md
  docs/spec/22_traceability.md

WHAT TO BUILD
A GitHub Actions workflow at .github/workflows/ci.yml, plus the package.json
scripts it invokes. Minimum steps: install, lint, build. Later tasks (T2-T7)
add the migration guard, pre-push hook, backup verification, static checks and
secret scanning — do not build those now.

DONE WHEN, both demonstrated with output:
  1. A PR run passes on a clean checkout with no local database.
  2. A deliberately broken commit FAILS that run.
A gate that has never refused anything is untested. Show both directions.

DO NOT
- Do not copy the CI workflow from the legacy repo (synclairebarrettllc/
  GBL-DOT-COM) blind. Its equivalent workflow is currently red and the cause
  has never been established. Take its structure if useful; verify everything.
- Do not start T2-T7. One task, one PR.
- Do not commit to main.

IF CI FAILS AND YOU DO NOT KNOW WHY
Get the failing step name and the first lines of its log before changing
anything. That failure has already been misdiagnosed twice in this project by
people reasoning from the diff instead of reading the log. Rework limit
applies: three failed cycles, then stop and report.

REPORT BACK
- Both done-when criteria with the run output proving each
- The workflow file
- Anything in the specification that was wrong, ambiguous, or missing
```

---

## After T1

Same template, next task. The phase feed changes — see the **Context feed**
table in `docs/spec/24_build-tasks.md`.

**Two documents stay in every feed:** `20_decisions.md`, because a task without
the policy values will invent them; and `22_traceability.md`, because a builder
who cannot see why a constraint exists will optimise it away.

**Do not feed `23_verification-handoff.md` to a builder.** It instructs the
reader to attack the code rather than write it. It goes to whoever verifies,
and that must not be the session that wrote the code.
