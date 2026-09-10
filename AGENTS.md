# AGENTS.md — GBL Backend Rebuild

Read this before doing anything.

This repository is the **new GBL backend**. It is a fresh build. There is no
legacy code here and none is being ported.

---

## Start here

**Open one task bundle. Do not read the whole specification.**

[`docs/tasks/`](docs/tasks/) holds one self-contained file per task — the task,
the specification sections it needs, the decision values it must use, and the
incidents behind its rules. **Average 1,124 words against a 45,000-word
specification.** Start with [`docs/tasks/README.md`](docs/tasks/README.md) for
the list, then open exactly the task you are building.

Reading `docs/spec/` end to end will exhaust your context before you write a
line of code. Go there only when a bundle is missing something — and if you do,
say so in your report, because it means the generator needs fixing.

The full specification is in [`docs/spec/`](docs/spec/), starting at
[`docs/spec/00_README.md`](docs/spec/00_README.md).

25 documents. It is the single build specification — there is no second one. If
another document ever disagrees with it, stop and escalate rather than picking a
reading.

**Your task queue is [`docs/tasks/README.md`](docs/tasks/README.md)** — T1
through T31 in dependency order, one bundle each. Work them in order. Do not
batch them, and do not open more than the bundle you are on.

### Before writing code

1. **[`docs/spec/20_decisions.md`](docs/spec/20_decisions.md) Part 2** — every
   policy item has a specified value. **Nothing blocks you.** Build what it says.
   Do not substitute a value you prefer: that converts a league decision into an
   undocumented default, which is exactly how the previous system acquired rules
   nobody agreed to. If something has **no** stated value, raise it — do not fill
   it in.

2. **[`docs/spec/21_implementation-order.md`](docs/spec/21_implementation-order.md)**
   — the build sequence and why it is in that order. It is dependency order, not
   preference.

3. **[`docs/spec/22_traceability.md`](docs/spec/22_traceability.md)** — every rule
   traced to the incident that caused it. When a rule looks excessive, this is
   where you find out what it cost.

---

## Non-negotiables

Standing constraints. Not defaults to weigh against convenience.

- **One task = one branch = one PR.** No agent works directly on `main`.
- **No direct push to production. Ever.**
- **Zero credentials** in source, commits, client code, or logs.
- **Migrations apply before the code that reads them.** This took the previous
  site down twice in one day — the second time during live stat entry.
- **Attempted ≠ verified.** "Done" requires evidence: a command and its output,
  asserting the resulting state. Not "it ran without errors" — every major defect
  in the previous system ran without errors.
- **Three failed fix/verify cycles on one piece, then stop and escalate** with a
  root-cause hypothesis and evidence. Do not guess a fourth time.
- **You do not verify your own work.** A piece is verified by a session with no
  context from the one that built it
  ([`docs/spec/23_verification-handoff.md`](docs/spec/23_verification-handoff.md)).

---

## Build order, in one line

**Rails before domain code.** Stage 0 is CI, the migration guard, the pre-push
hook, verified backups, static checks and secret scanning — and its exit criterion
is that **every gate has refused something**. A gate that has never said no is
untested. That is not a formality: the previous project's backup script reported
success on a garbage snapshot for weeks, and was caught only by deliberately
feeding it a corrupt database.

---

## The four defects that define this build

Read `22_traceability.md` for the full matrix. These four are why the rebuild
exists:

1. **Stat lines saved, nothing recomputed.** A game holds five real stat lines
   worth 81 points and still reads `scheduled 0-0`. Writing a stat line **must**
   derive the score in the same transaction.
2. **Scoring stored as combined field goals.** "3 twos and 2 threes" produced
   **8 points instead of 12**. Store 2PM and 3PM separately; derive the rest.
3. **Attempts required by validation, never collected in practice.** `0` was read
   as "zero attempts" rather than "not tracked", and **every real stat line was
   rejected**. `NULL` and `0` are different values with different meanings.
4. **Structure inferred from display text.** Bracket progression read round
   *names*. Progression is a foreign key, never a label.

---

## The legacy system

Lives in a separate repository (`GBL-DOT-COM`). It is **reference and evidence
only** — it is where the FACT citations in the specification come from.

- Do not port its code.
- Do not import from it.
- Do not treat its behaviour as a requirement. Every legacy behaviour the
  specification references carries an explicit verdict: PRESERVE, ADAPT, BUILD
  FRESH, REPLACE or RETIRE.

The legacy app is **live and the league depends on it.** Nothing in this
repository changes it.

---

## Platform

Cloudflare Workers + D1 + Pages, with Durable Objects + WebSockets for the live
stat tracker. Decided — see O7 in `docs/spec/20_decisions.md`.
