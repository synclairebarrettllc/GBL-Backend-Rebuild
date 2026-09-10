# 24 — Build Task Queue

**For the builder.** `21_implementation-order.md` gives stages; a stage is far
too large for one PR. This is the rolling queue of **PR-sized tasks**, in order.

**REQUIREMENT.** One task = one branch = one PR. Do not batch tasks. Do not start
a task whose predecessor is unmerged unless it is marked independent.

**Each task states its own definition of done.** "Done" means that criterion is
demonstrated with output, not asserted (S33).

---

## Task format

```
T<n> — <title>                         [BLOCKED | READY | INDEPENDENT]
Why        one line — what breaks without it
Scope      exactly what changes; what must NOT change
Done when  the demonstrable criterion
Spec       the governing clause
```

---

## Stage 0 — Rails

Most of Stage 0 already exists in this repository. **Verified 2026-09-09:** CI
workflow, migration guard wired to `prebuild`, tracked pre-push hook via
`core.hooksPath`, verified backup script with its known-bad-database test in CI.

What remains:

### T1 — Make CI green [BLOCKED — needs the failing log]

**Why.** Every later task's PR gets an honest pass/fail signal only if the
baseline is green. Adding steps to a red pipeline buries the original failure.

**Scope.** `.github/workflows/ci.yml` only. No source changes.

**Done when.** A PR run passes all steps, and the fix names the actual root cause
rather than a plausible one.

**Note — do not guess at this.** It has already been diagnosed wrong twice: a
`webapp/` subdirectory assumption was a real defect but not the current failure,
and a clean-clone reproduction passes all seven steps locally. **Get the failing
step name and its first log lines before changing anything.** Rework limit
applies (S31).

---

### T2 — Add static checks to CI [BLOCKED by T1]

**Why.** These enforce rules no runtime test can, because they are about what
code exists. Each corresponds to a defect that was invisible until production.

**Scope.** New CI step plus a `scripts/static-checks.sh`. Grep-level is
sufficient — this must run in seconds.

Start with the checks that are meaningful against the **current** codebase, and
add the rest as the new backend appears:

| Check | Rule |
|---|---|
| `no-string-sql` | All SQL parameterised |
| `no-secrets` | No credential in tree |
| `status-checks-present` | Every status column has a `CHECK` constraint |

**Done when.** Each check **refuses a deliberately planted violation** in a
scratch commit, and passes on `main`. A check that has never rejected anything is
untested.

**Spec.** `18_testing.md` §3.

---

### T3 — Add secret scanning to CI [INDEPENDENT of T2, blocked by T1]

**Why.** Standing constraint: zero credentials in source, commits, client code,
or logs. The repository is private because it contains real player names — the
same care applies to keys.

**Scope.** CI step, plus wiring into `.githooks/pre-push`.

**Done when.** A planted test credential is caught by both the hook and CI, and
removed afterward.

**Spec.** `16_security.md` §6.

---

### T4 — Confirm `main` branch protection [INDEPENDENT]

**Why.** S27 — no agent works directly on `main`. Currently unverified from the
CLI.

**Scope.** Repository settings, not code. Requires: no direct pushes, CI
required, PR required.

**Done when.** A direct push to `main` is refused by the remote.

**Spec.** `17_operations.md` §4.

---

### Stage 0 exit criterion

**Every gate has refused something.** Not "every gate exists." A gate that has
never said no is untested — this is how the backup script came to report success
on a garbage snapshot.

---

## D-REPO — Where the new backend lives — DECIDED

**`GBL-backend-rebuild`** — a separate repository, confirmed to exist and
currently empty apart from a README.

Rationale: clean separation from the 8,373-line legacy route file, which cannot
be accidentally imported from a different repository. The legacy app stays live
and untouched under its own rails.

**Consequence — T1–T4 apply to the new repo, not this one.** The rails here are
proven and can be copied, but each must **refuse something in the new repo**
before Stage 0 exits there. A gate copied but never fired is not a gate.

**Exception — T1 (make CI green) still belongs to this repository too.** The red
pipeline here is a live problem regardless of where the rebuild happens.

---

## Stage 1 — Schema and identity

Do not start until Stage 0 exits and D-REPO is answered.

### T5 — Core schema DDL

**Scope.** Every table in `05_database.md` with **every** `CHECK`, partial unique
index, and `RESTRICT`. Constraints ship **with** the tables — constraints added
after data exists get relaxed to fit the data.

**Done when.**
- Migrations apply cleanly to a fresh database
- `season.single-active` is enforced **by the database**: inserting a second
  active season fails at the SQL level, not in application code
- `PRAGMA foreign_keys = ON` is asserted per connection and tested
- No score column exists on `game`; no stored totals or records anywhere

**Spec.** `05_database.md`, `04_state-machines.md`.

---

### T6 — IdentityService

**Scope.** Person, Player, external refs. `createPerson`,
`createPlayerForSeason`, `linkPlayerToPerson`, `setExternalRef`.

**Done when.** `identity.one-per-season` and `identity.immutable` pass, and
`linkPlayerToPerson` **cannot be invoked automatically** — identical names
produce a suggestion, never a link.

**Spec.** `06_mutations.md` §4.1.

---

### T7 — Season, Team, Roster, Venue, Config services

**Scope.** `06_mutations.md` §4.2, §4.3, §4.10.

**Done when.** A season cannot activate with an incomplete config, **and the
rejection names the missing keys**. Ending a roster membership changes no stat
line.

**Spec.** `06_mutations.md`, `13_configuration.md` §6.

---

## Then

`21_implementation-order.md` Stage 2 onward — games, results, statistics, and
the derivation edge. Decompose each stage into tasks in this format as it is
reached, rather than planning the whole build in advance against decisions that
are still open.

---

## Rules for working this queue

**REQUIREMENT — implement the stated value; never substitute your own.** Every
policy item in `20_decisions.md` Part 2 has a value: DECIDED (technical) or
DEFAULT (league policy, set so you are not blocked). Write it into season config
explicitly — the system must still **fail loudly** on a missing key, because a
specified default is not the same thing as a silent code fallback.

If you hit a case with **no** stated value, that is a specification gap. Raise it;
do not fill it.

**REQUIREMENT — verification is not self-verification.** A completed task is
verified by a session with no context from the one that built it
(`23_verification-handoff.md`).

**REQUIREMENT — three failed fix/verify cycles, then stop** and escalate with a
root-cause hypothesis and evidence (S31).

**REQUIREMENT — the legacy app stays live.** The league depends on it. No task in
this queue modifies legacy behaviour unless it says so explicitly.
