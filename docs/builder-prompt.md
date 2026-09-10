# Builder prompts

**Hand over a stage, not a task.** Ten stages, not thirty-one tasks. Each stage
is internally coherent, has a written exit criterion, and ends somewhere you can
actually check.

Codex still opens one PR per task inside a stage — that is S27 and it is how a
bad task gets reverted without losing the good ones — but you prompt once per
stage and review once per stage.

| Stage | Tasks | What you get at the end |
|---|---|---|
| **0** | T1–T7 | The gates. **After this you stop reviewing code by hand** |
| **1** | T8–T10 | Schema, identity, seasons, teams, rosters, config |
| **2** | T11–T14 | Scheduling, stat lines, results, **the derivation edge** |
| **3** | T15–T17 | The live courtside tracker |
| **4** | T18–T19 | Standings and tiebreaks |
| **5** | T20–T22 | Seeding and brackets |
| **6** | T23–T25 | Registration |
| **7** | T26–T27 | Schedule generation and bulk reschedule |
| **8** | T28–T30 | Public API, admin dashboard, AI surface |
| **9** | T31 | Full-season acceptance, in CI |

---

## Why Stage 0 first, and why it is the one that buys you time

You are not an engineer and should not be reading diffs. Stage 0 is what
replaces you as the reviewer:

- CI runs the whole test suite on every PR
- the migration guard refuses code that reads a column the database lacks
- static checks refuse a second home for any fact, a stored total, a score
  column on `game`, or SQL outside the data layer
- the backup verifier refuses a bad snapshot
- the contradiction scan refuses a spec that disagrees with itself

**Once those exist, the machine reviews Codex, not you.** That is why it is
seven tasks of plumbing before any basketball gets built, and why going faster
starts by going slower once.

---

## Stage 0 — ready to paste

```
Repository: synclairebarrettllc/GBL-Backend-Rebuild

Read AGENTS.md first. You are on Job A: building the new backend. This repo
currently contains only the specification — no application code, no CI, no
scripts. You are building the rails that every later stage depends on.

STAGE 0 — Rails. Tasks T1 through T7.
Full definitions in docs/spec/24_build-tasks.md. Read the whole Stage 0
section before starting.

LOAD:
  docs/spec/24_build-tasks.md   (Stage 0)
  docs/spec/17_operations.md    (the gate chain, backup criteria, deploy order)
  docs/spec/18_testing.md       (what counts as evidence; the static checks)
  docs/spec/16_security.md      (§6 secrets)
  docs/spec/20_decisions.md
  docs/spec/22_traceability.md

BUILD, in order, one PR per task:
  T1  CI workflow (install, lint, build)
  T2  Migration guard, wired as npm prebuild
  T3  Pre-push hook, tracked, enabled via core.hooksPath
  T4  Verified backup script
  T5  Static checks
  T6  Secret scanning
  T7  Branch protection on main

THE EXIT CRITERION IS NOT "THESE EXIST". IT IS THAT EACH ONE HAS REFUSED
SOMETHING. For every gate, show me the output of it rejecting a deliberately
bad input, and then passing on a good one. Both directions, every gate:
  - CI fails a deliberately broken commit
  - the migration guard fails a build with an unapplied migration, AND still
    builds on a fresh clone with no local database
  - the pre-push hook blocks a real push
  - the backup script refuses a corrupt database and leaves no file behind
  - each static check rejects a planted violation
  - the secret scanner catches a planted test credential
  - a direct push to main is refused by the remote

A gate that has never said no is untested. The legacy backup script reported
success on a garbage snapshot for weeks and was only caught by deliberately
feeding it a corrupt database.

RULES
- One task = one branch = one PR. Never commit to main.
- Build what docs/spec/20_decisions.md says. If you need a value it does not
  contain, stop and say so. Do not choose one.
- Done means evidence: the command and its output, asserting the resulting
  state. Not "it ran without errors".
- Three failed fix/verify cycles on one thing, then stop and report with a
  root-cause hypothesis. Do not guess a fourth time.

DO NOT
- Do not copy the legacy repo's CI workflow (synclairebarrettllc/GBL-DOT-COM)
  blind. Its equivalent is currently red, the cause was never established, and
  it has been misdiagnosed twice by people reasoning from the diff instead of
  reading the log. Take its structure; verify everything.
- Do not start Stage 1. Stage 0 ends when every gate has refused something.

REPORT BACK
- One block per gate: the refusal output, then the pass output
- Anything in the specification that was wrong, ambiguous, or missing
```

---

## "Just build it" — the whole thing, one prompt

Use this when you want the full backend in one handoff rather than stage by
stage. It works because the specification is complete and because it makes the
build **verify itself** — you are not reviewing 10,000 lines of code, the
acceptance suite is.

```
Repository: synclairebarrettllc/GBL-Backend-Rebuild

Read AGENTS.md, then docs/spec/00_README.md.

Build the whole backend. The complete specification is in docs/spec/ — 25
documents, every architectural rule traced to the failure that caused it. The
task queue is docs/spec/24_build-tasks.md, T1 through T31, in dependency order.

BUILD IN THIS ORDER. It is not negotiable, and here is why:

1. STAGE 0 FIRST (T1-T7): CI, migration guard, pre-push hook, verified backup,
   static checks, secret scanning, branch protection. Nobody is reading your
   diffs. These gates are the review. Do not skip them to get to the
   interesting part.
   Each gate must REFUSE something before you move on — show a bad input being
   rejected, then a good one passing. A gate that has never said no is untested.

2. THEN THE ACCEPTANCE SUITE (T31, from docs/spec/19_acceptance.md): write the
   45-step full-season scenario as FAILING tests, before the code that satisfies
   them. That suite is the definition of done for this entire build.

3. THEN EVERYTHING ELSE (T8-T30) until the acceptance suite is green.

RULES
- One task = one branch = one PR. Never commit to main.
- Every policy value is in docs/spec/20_decisions.md. Build what it says. If you
  need a value it does not contain, STOP AND ASK. Do not pick something
  reasonable — that is how the previous system acquired rules nobody agreed to.
- Migrations apply before the code that reads them. This took the old site down
  twice in one day, the second time during live stat entry.
- Read docs/spec/22_traceability.md before deleting or simplifying any
  constraint. Every one of them is there because something broke.
- Three failed fix/verify cycles on one thing, then stop and report with a
  root-cause hypothesis. Do not guess a fourth time.

DO NOT TELL ME IT IS DONE UNTIL THE ACCEPTANCE SUITE PASSES.
Specifically these three, which are where a plausible-looking build fails:
  - reversing a correction restores a byte-identical standings table
  - renaming every bracket round label changes nothing
  - deleting every projection and recomputing gives byte-identical results

REPORT BACK
- The acceptance suite output
- Every gate's refusal output
- Anything in the specification that was wrong, ambiguous, or missing. You are
  the first person to actually use it. Say what did not hold up.
```

**Why acceptance-tests-first matters here.** In a one-shot build nobody reads
the code, so the only thing standing between you and a subtly wrong system is a
suite that was written from the specification rather than from the
implementation. Written afterwards, tests describe what the code does. Written
first, they describe what the league needs.


---

## Template for Stage 1 onward

```
Repository: synclairebarrettllc/GBL-Backend-Rebuild
Read AGENTS.md first. Job A.

STAGE <n> — <name>. Tasks <Tx>–<Ty>.
Read that stage in docs/spec/24_build-tasks.md before starting.

LOAD: <phase feed from the Context feed table in 24_build-tasks.md>
      plus docs/spec/20_decisions.md and docs/spec/22_traceability.md, always.

BUILD one PR per task, in order. Each task's "Done when" is the gate — show
the output that proves each criterion, not a description of the code.

RULES
- One task = one branch = one PR. Never commit to main.
- Build the values in 20_decisions.md. If one is missing, stop and say so.
- Migrations apply before the code that reads them.
- Three failed fix/verify cycles, then stop and report.

DO NOT start the next stage.

REPORT BACK: each "Done when" criterion with its proving output; anything in
the specification that was wrong, ambiguous, or missing.
```

---

## The one thing to check in every report

If a report says "done, tests pass" without output showing a **failure** being
caught, send it back. That is the shape of every defect in
`22_traceability.md` — the thing that ran without errors and did nothing. The
admin delete button returned success for months with no handler behind it.

---

## Not in any builder prompt

`23_verification-handoff.md` goes to whoever verifies a stage, and that must not
be the session that built it. It instructs the reader to attack the code rather
than write it.
