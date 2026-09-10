# 24 — Build Task Queue

**For the builder.** `21_implementation-order.md` gives stages; a stage is far
too large for one PR. This is the rolling queue of **PR-sized tasks**, in order.

**REQUIREMENT.** One task = one branch = one PR. Do not batch tasks. Do not start
a task whose predecessor is unmerged unless it is marked `INDEPENDENT`.

**Each task states its own definition of done.** "Done" means that criterion is
demonstrated with output, not asserted (S33).

---

## Which repository a task targets

Two repositories are in play, and **every task names which one it belongs to.** A
task in the wrong repository is not a small mistake — the two have different rules
and different risk.

| Tag | Repository | What it is |
|---|---|---|
| **[REBUILD]** | `GBL-Backend-Rebuild` | The new backend. This repo. Where the build happens |
| **[LEGACY]** | `GBL-DOT-COM` | The live site the league depends on. Reference and evidence only |

**Evidence citations throughout the specification** — `src/index.tsx:3082`,
`scripts/import-recleague.cjs:409-420`, `migrations/0029_*.sql` — refer to
**[LEGACY]** paths. They are the proof behind a rule, not files in this
repository. Do not go looking for them here.

---

## Task format

```
T<n> — <title>                    [REPO] [READY | BLOCKED by … | INDEPENDENT]
Why        one line — what breaks without it
Scope      exactly what changes; what must NOT change
Done when  the demonstrable criterion
Spec       the governing clause
```

---

## Stage 0 — Rails [REBUILD]

**Nothing exists yet. Every rail is built here, from zero.**

The legacy repository has working, proven implementations of most of these. They
are **good starting material and should be copied rather than reinvented** — each
exists because of a specific incident, and rewriting from scratch re-earns those
incidents.

| Rail | Proven implementation to start from [LEGACY] | Task |
|---|---|---|
| CI workflow | `.github/workflows/ci.yml` — 7 steps | T1 |
| Migration guard | `scripts/check-migrations.sh`, wired as npm `prebuild` | T2 |
| Pre-push hook | `.githooks/pre-push`, enabled via `core.hooksPath` | T3 |
| Verified backup | `scripts/db-backup.sh` | T4 |
| Static checks | — new | T5 |
| Secret scanning | — new | T6 |
| Branch protection | — settings | T7 |

**REQUIREMENT — a copied gate is not a working gate.** Each must **refuse
something in this repository** before Stage 0 exits. The legacy backup script
reported success on a garbage snapshot for weeks and was caught only by
deliberately feeding it a corrupt database.

---

### T1 — Stand up CI [REBUILD] [READY]

**Why.** Every later task's PR needs an honest pass/fail signal. S29 makes CI
mandatory, not advisory.

**Scope.** `.github/workflows/ci.yml` plus the `package.json` scripts it invokes.
Minimum steps: install → lint → build. Later tasks add the rest.

**Done when.** A PR run passes on a clean checkout **with no local database**,
**and** a deliberately broken commit fails it. Both directions demonstrated.

**Note.** The equivalent workflow in [LEGACY] is currently red for reasons not yet
established. **Do not copy it blind.** Take its structure; if the same failure
appears here, get the failing step name and its first log lines before changing
anything — that failure has already been misdiagnosed twice, and S31 applies.

**Spec.** `17_operations.md` §3.

---

### T2 — Migration guard [REBUILD] [BLOCKED by T1]

**Why.** **This took the legacy site down twice in one day** — code shipped
reading columns the database did not have. The second outage killed public
leaderboards and standings *while the league owner was entering live stats*.

**Scope.** `scripts/check-migrations.sh`, wired as npm `prebuild` so it cannot be
skipped by forgetting, plus a CI step.

**Done when.**
- A build with unapplied migrations **fails**
- A fresh clone with **no local database still builds** — a guard that breaks CI
  gets disabled, and a disabled guard protects nothing
- Both demonstrated with output

**Spec.** `17_operations.md` §2.

---

### T3 — Pre-push hook [REBUILD] [BLOCKED by T2]

**Why.** Catches the same class of failure before it reaches the remote, where
recovery is cheap.

**Scope.** `.githooks/pre-push`, **tracked in the repository** and enabled via
`core.hooksPath` so it is shared rather than reinvented per machine. Runs the
migration guard, lint, and build.

**Done when.** It **blocks a real push** that violates one of its checks.

**Spec.** `17_operations.md` §3.

---

### T4 — Verified backup script [REBUILD] [INDEPENDENT of T2–T3]

**Why.** Every migration and bulk operation is gated on a verified backup. The
first legacy implementation of this **reported success on a garbage snapshot** —
its row-count loop skipped every check on a table-less database, and its content
check compared two empty strings and called it a match.

**Scope.** `scripts/db-backup.sh`, plus a CI step that feeds it a known-bad
database.

**Done when** the snapshot is kept **only if** it passes all of:

- taken via the SQLite online backup API, **never** a file copy under WAL
- `PRAGMA integrity_check` returns `ok`
- `PRAGMA foreign_key_check` returns nothing
- per-table row counts match source
- content checksums match
- a non-empty floor
- WAL folded — no `-wal`/`-shm` sidecars, so the file is self-contained

**and a failure discards the file.** A file that exists must mean a backup exists.

**Prove the refusal.** Feed it a corrupt database in CI and confirm no file
survives.

**Spec.** `17_operations.md` §5, `14_import-migration.md` §7.

---

### T5 — Static checks [REBUILD] [BLOCKED by T1]

**Why.** These enforce rules no runtime test can, because they are about what code
exists. Each maps to a defect that was invisible until production.

**Scope.** `scripts/static-checks.sh` plus a CI step. Grep-level is sufficient —
this must run in seconds.

Add each check as the code it governs appears. Full list in `18_testing.md` §3;
the ones meaningful from day one:

| Check | Rule |
|---|---|
| `no-string-sql` | All SQL parameterised |
| `no-sql-in-routes` | No SQL outside the data layer |
| `status-checks-present` | Every status column has a `CHECK` constraint |
| `no-stored-totals` | No column stores a season total, record, or rank |
| `no-score-on-game` | `game` has no score column |

**Done when.** Each check **refuses a deliberately planted violation** and passes
on `main`. A check that has never rejected anything is untested.

**Spec.** `18_testing.md` §3.

---

### T6 — Secret scanning [REBUILD] [INDEPENDENT of T5, blocked by T1]

**Why.** Standing constraint: **zero credentials** in source, commits, client
code, or logs (S35).

**Scope.** A CI step over full history, plus wiring into the T3 hook.

**Done when.** A planted test credential is caught by **both** the hook and CI,
then removed.

**Spec.** `16_security.md` §6.

---

### T7 — Branch protection [REBUILD] [INDEPENDENT]

**Why.** S27 — no agent works directly on `main`.

**Scope.** Repository settings, not code: no direct pushes, CI required, PR
required.

**Done when.** A direct push to `main` is **refused by the remote**.

**Note.** The specification and `AGENTS.md` were seeded directly to `main` before
this task existed. That was repo bootstrap, not feature work. After T7, nothing
else goes to `main` without a PR.

**Spec.** `17_operations.md` §4.

---

### Stage 0 exit criterion

**Every gate has refused something.** Not "every gate exists." A gate that has
never said no is untested — this is how the backup script came to report success
on a garbage snapshot.

---

## D-REPO — Where the new backend lives — DECIDED

**`GBL-Backend-Rebuild`** — this repository.

Rationale: clean separation from the 8,373-line legacy route file, which cannot be
accidentally imported from a different repository. The legacy app stays live and
untouched under its own rails.

---

## Stage 1 — Schema and identity [REBUILD]

Do not start until Stage 0 exits.

### T8 — Core schema DDL [BLOCKED by Stage 0]

**Scope.** Every table in `05_database.md` with **every** `CHECK`, partial unique
index and `RESTRICT`. Constraints ship **with** the tables — constraints added
after data exists get relaxed to fit the data.

**Done when.**
- Migrations apply cleanly to a fresh database
- `season.single-active` is enforced **by the database**: a second active season
  fails at the SQL level, not in application code
- `PRAGMA foreign_keys = ON` is asserted per connection **and tested** — the
  legacy cascade silently did not fire because the SQLite CLI defaults it off
- No score column on `game`; no stored totals, records or ranks anywhere

**Spec.** `05_database.md`, `04_state-machines.md`.

---

### T9 — IdentityService [BLOCKED by T8]

**Scope.** Person, Player, external refs: `createPerson`,
`createPlayerForSeason`, `linkPlayerToPerson`, `setExternalRef`.

**Done when.** `identity.one-per-season` and `identity.immutable` pass, and
`linkPlayerToPerson` **cannot be invoked automatically** — identical names produce
a suggestion, never a link. Name-based matching in the legacy importer made one
human into two players carrying 4 and 5 stat lines across their 4 games.

**Spec.** `06_mutations.md` §4.1.

---

### T10 — Season, Team, Roster, Venue, Config services [BLOCKED by T9]

**Scope.** `06_mutations.md` §4.2, §4.3, §4.10.

**Done when.** A season cannot activate with an incomplete config **and the
rejection names the missing keys**. Ending a roster membership changes no stat
line.

**Spec.** `06_mutations.md`, `13_configuration.md` §6.

---

## Then

`21_implementation-order.md` Stage 2 onward — games, results, statistics, and the
derivation edge. Decompose each stage into tasks in this format as it is reached,
rather than planning the whole build against decisions that may still move.

---

## Out of band — not this queue

**[LEGACY] CI is red.** Cause unknown; needs the failing step name and log. It
does not block anything here, and it is **not** the rebuild's work. Tracked
separately so it is not lost.

---

## Rules for working this queue

**REQUIREMENT — implement the stated value; never substitute your own.** Every
policy item in `20_decisions.md` Part 2 has a value: DECIDED (technical) or
DEFAULT (league policy, set so you are not blocked). Write it into season config
explicitly — the system must still **fail loudly** on a missing key, because a
specified default is not a silent code fallback.

If you hit a case with **no** stated value, that is a specification gap. Raise it;
do not fill it.

**REQUIREMENT — verification is not self-verification.** A completed task is
verified by a session with no context from the one that built it
(`23_verification-handoff.md`).

**REQUIREMENT — three failed fix/verify cycles, then stop** and escalate with a
root-cause hypothesis and evidence (S31).

**REQUIREMENT — the legacy app stays live.** The league depends on it. No task in
this queue touches it.
