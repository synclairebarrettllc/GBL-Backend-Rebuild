# 24 — Build Task Queue

**For the builder.** `21_implementation-order.md` gives stages; a stage is far
too large for one PR. This is the **complete queue** of PR-sized tasks, in order —
T1 through T31, Stage 0 to acceptance. It is not rolling and it does not defer
decomposition to later; the execution interface is finished before the build
starts, because "one task = one branch = one PR" only works if the tasks exist.

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

## Stage 2 — Games, results, statistics [REBUILD]

**The heart of the build.** This is where the legacy system's central failure
lived, and everything downstream reads what this stage produces.

### T11 — ScheduleService, individual operations [BLOCKED by T10]
**Scope.** `scheduleGame`, `rescheduleGame`, `cancelGame`, `deleteGame`
(`06_mutations.md` §4.4). Bulk operations are Stage 7 — do not build them here.
**Done when.** Two games cannot occupy one `(venue, court, starts_at)` — **rejected
by the database**, not by application code. A team's second game in one
**league-local** day is rejected. Both errors name the conflicting game id.
Deleting a game that has stat lines is refused and names the alternative.
**Spec.** `10_scheduling.md` §3, §6.

### T12 — StatsService [BLOCKED by T11]
**Scope.** `player_game_stat_line` writes: 2PM/3PM/FTM stored, attempts nullable,
points and FGM derived. Idempotent by `operation_id`.
**Done when.** `stats.scoring-arithmetic` passes — 3 twos + 2 threes = **12**.
`stats.makes-only-line-accepted` passes — a line with makes and no attempts saves.
`stats.attempts-null-vs-zero` passes — `NULL` attempts yields `NULL` percentage,
`0` yields `0`. No column anywhere stores a season total.
**Spec.** `07_statistics.md` §1–§3.

### T13 — GameResultService and the derivation edge [BLOCKED by T12]
**Why.** The single missing edge in the legacy system. Game 1971 holds five real
stat lines worth 81 points and reads `scheduled 0-0`.
**Scope.** `game_result` as sole score authority; `result_source` per ADR-010;
stat write → score derivation **in the same transaction**.
**Done when.** `stats.derivation-edge`, `adr010.stat-lines-produce-score`,
`adr010.derived-overwrite-refused`, `adr010.replay-does-not-alter-result` and
`result.entered-refused-with-stats` all pass. Schema check: `game` has no score
column.
**Spec.** `08_game-results.md` §2–§3.

### T14 — Finalisation and correction [BLOCKED by T13]
**Scope.** `finalizeGame`, `correctFinalizedGame`, discrepancy detection and
both-value recording (O5 default `warn`).
**Done when.** Finalisation is operator-driven only — no time-based or automatic
path exists. A correction returns the game to `completed` and cascades. A box
score that disagrees with a recorded score is **detected and recorded with both
values**, and does not block finalisation.
**Spec.** `08_game-results.md` §4, §6, §7.

---

## Stage 3 — The live tracker [REBUILD]

**Built early deliberately.** It has no legacy precedent, carries the most product
risk, and is the thing the league actually asked for (S3).

### T15 — Per-game capability tokens [BLOCKED by T14]
**Scope.** Token issuance, scoping, hashing at rest, expiry, revocation,
rate limiting.
**Done when.** `sec.tracker-scope`, `sec.tracker-no-escalation`,
`sec.tracker-expiry` and `sec.token-hashed` pass. **No tracker endpoint accepts a
`game_id` parameter** — the scope comes from the token, so there is nothing to
tamper with.
**Spec.** `16_security.md` §2, `15_api.md` §5.

### T16 — Tracker write surface [BLOCKED by T15]
**Scope.** Stat entry, `scheduled → in_progress`, submit to `completed`.
**Progressive persistence** — every increment is a write, no client-side buffer.
**Done when.** `tracker.progressive-save` passes with a **real interruption**:
enter stats, kill the tab mid-game, reopen, nothing lost. `tracker.idempotent-retry`
passes. `tracker.cannot-finalize` passes.
**Spec.** `07_statistics.md` §5.

### T17 — Real-time propagation [BLOCKED by T16]
**Scope.** Durable Objects + WebSockets (O7). Stat writes reach public read views
without a refresh.
**Done when.** A stat entered courtside appears on a public view within seconds,
with no page reload, demonstrated on two simultaneous clients.
**Spec.** `07_statistics.md` §5.

---

## Stage 4 — Standings [REBUILD]

### T18 — StandingsService as a projection [BLOCKED by T14]
**Scope.** Records computed from finalised games. **No mutation methods.**
Config-version stamping.
**Done when.** `standings.no-stored-record` (schema check: no wins/losses/rank
column exists), `standings.recompute-equality`, `standings.deterministic` and
**`standings.correction-reverses`** pass. That last one is the regression test for
the legacy accumulator — an accumulator passes the forward test and fails this.
**Spec.** `09_standings.md` §1–§3.

### T19 — Tiebreak chains [BLOCKED by T18]
**Scope.** The full criterion vocabulary, configurable and reorderable chains
(S20), separate regular-season and playoff chains, multi-team strategies with
`sub_table_restart` as default (O3), deterministic `coin_flip` fallback.
**Done when.** `standings.tiebreak-order-applied`, `standings.tiebreak-total-order`,
`standings.coin-flip-stable`, `standings.multi-team-strategy` and
`standings.explains-adjacent` pass. Every tie resolves to a stable order and the
engine **names the criterion that separated any adjacent pair**.
**Spec.** `09_standings.md` §4.

---

## Stage 5 — Playoffs [REBUILD]

### T20 — Seeds with basis snapshot [BLOCKED by T19]
**Scope.** `finalizeSeeds` as an explicit operator action; `basis_snapshot`
written in the **same transaction**; durability per O4 default.
**Done when.** `seed.basis-snapshot-written` and `seed.separate-chain` pass. A
post-seeding correction raises a **flagged discrepancy**, never a silent reseed.
**Spec.** `11_playoffs.md` §3.

### T21 — Bracket structure [BLOCKED by T20]
**Scope.** `generateBracket` creating **every** match and **every**
`winner_advances_to_match_id` edge before the bracket leaves `draft`. Byes as
already-decided matches.
**Done when.** `bracket.structural-progression` passes — **rename every round
label in the database and no bracket behaviour changes**. That is the definitive
regression test for the legacy defect. `bracket.structure-complete-before-seed`
and `bracket.no-parallel-table` pass.
**Spec.** `11_playoffs.md` §1–§4.

### T22 — Propagation and bounded correction [BLOCKED by T21]
**Scope.** One hop per transaction along FK edges; series decided from game
results; correction propagation bounded.
**Done when.** `bracket.propagation`, `bracket.series-derived`,
`bracket.correction-no-change-no-propagate` and **`bracket.correction-bounded`**
pass. Correct a first-round result and diff the whole database: every match not
reachable along progression edges is **byte-identical**.
**Spec.** `11_playoffs.md` §5.

---

## Stage 6 — Registration [REBUILD]

### T23 — Public submission [BLOCKED by T10]
**Scope.** Walk-up mobile flow, minimum required fields, progressive persistence,
idempotent by `operation_id`, rate limited.
**Done when.** `registration.submit-creates-only-registration` passes — **no
Person, no Player, no membership on submit**. `registration.idempotent-submit`
and `registration.progressive-save` pass.
**Spec.** `12_registration.md` §2, §6.

### T24 — Acceptance and assignment [BLOCKED by T23]
**Scope.** Operator-confirmed identity matching; `assignToTeam` creating Person,
Player and RosterMembership in **one transaction**.
**Done when.** `registration.no-auto-match` passes — identical names produce a
**suggestion, never a link**. `registration.assign-atomic` passes under fault
injection at each of the four rows.
**Spec.** `12_registration.md` §3, §7.

### T25 — Eligibility, waiver and PII [BLOCKED by T24]
**Scope.** Age verification against `age_as_of_date`; guardian signature required
under 18 (S38); waiver artefact slot with `document_version`; PII isolation.
**Done when.** `registration.age-as-of-date`, `registration.guardian-required`,
`registration.waiver-version-recorded`, `registration.no-payment-field`,
`registration.pii-not-public` and `registration.pii-not-logged` pass.
**Do not build a custom e-signature flow** (O11).
**Spec.** `12_registration.md` §4, §5, §8.

---

## Stage 7 — Bulk scheduling [REBUILD]

**After individual operations, never before.** Bulk operations are compositions;
composing unproven primitives multiplies their defects.

### T26 — Schedule generation as a dry run [BLOCKED by T11]
**Scope.** Parameter-driven generation (S21) returning a proposal plus a
constraint report. A separate explicit `commitSchedule` writes games.
**Done when.** `schedule.generate-is-dry-run` passes — `generate()` writes
nothing. An unsatisfiable constraint set **names the constraint and where**,
rather than returning an empty or partial schedule.
**Spec.** `10_scheduling.md` §4.

### T27 — Bulk rescheduling [BLOCKED by T26]
**Scope.** `bulkReschedule` — atomic, dry run by default, full change-set
emission for the G4 decision.
**Done when.** `schedule.bulk-atomic` passes under injected mid-operation
failure — **zero games moved**. `schedule.bulk-reports-all-conflicts` reports
every conflict at once, not one at a time.
**Spec.** `10_scheduling.md` §5.

---

## Stage 8 — Read surfaces [REBUILD]

### T28 — Public API [BLOCKED by T19]
**Scope.** Read endpoints with **deleted-row filtering in the data access layer,
by construction**. Pagination everywhere. Typed domain errors.
**Done when.** `api.deleted-filtered-everywhere` passes **by construction, not by
audit** — the legacy equivalent required auditing 62 sites and still missed 11.
`api.no-sql-in-routes`, `api.get-never-writes`, `api.null-percentages`,
`api.pagination-enforced` and `api.status-codes-truthful` pass.
**Spec.** `15_api.md` §4–§6.

### T29 — Admin dashboard [BLOCKED by T28]
**Scope.** Upcoming games front and centre; **a flag for played games missing
scores or stats** (S26).
**Done when.** `api.dashboard-flags-incomplete` passes. A game in game 1971's
condition — real stat lines, no result — appears on the dashboard **the same
day**, not months later in an audit.
**Spec.** `15_api.md` §5.

### T30 — AI read surface [BLOCKED by T28]
**Scope.** Authenticated, read-only (S12). No embedded chatbot.
**Done when.** It returns exactly what the public surface returns —
authentication controls **access, not scope**. `api.no-pii-public` passes against
this surface too.
**Spec.** `15_api.md` §5.

---

## Stage 9 — Acceptance [REBUILD]

### T31 — The full-season scenario [BLOCKED by T30]
**Scope.** All 45 steps of `19_acceptance.md` §2, automated, running in CI.
**Done when.** The scenario passes end to end, including the three hardest
assertions: reversing a correction restores a **byte-identical** standings table;
renaming every bracket round label changes **nothing**; deleting every projection
and recomputing produces **byte-identical** results.
**Spec.** `19_acceptance.md`.

**On completion:** the definition of done in `19_acceptance.md` §1 is satisfied
for every piece, and the specification's own claim — that a season can be run
correctly end to end — is demonstrated rather than asserted.

---

## Out of band — not this queue

**[LEGACY] CI is red.** Cause unknown; needs the failing step name and log. It
does not block anything here, and it is **not** the rebuild's work. Tracked
separately so it is not lost.

---

## Context feed — what to load for each task

Loading all 25 documents for every task wastes context and dilutes attention.
T8 writes DDL; it does not need the bracket engine. This table says what to load.

**Two rules that are not negotiable:**

1. **`20_decisions.md` is in every feed.** It holds every policy value. A task
   run without it will hit a `POLICY` slot it cannot resolve and invent a value —
   the exact failure the register exists to prevent.
2. **`22_traceability.md` is in every feed.** It is why the rules exist. A builder
   that cannot see why a constraint is there will optimise it away, and that is
   the mechanism behind most of the defects listed in it.

Everything else is loaded per phase.

| Phase | Tasks | Load, in addition to `20` + `22` |
|---|---|---|
| **Rails** | T1–T7 | `17_operations`, `18_testing`, `16_security` §6 |
| **Schema & identity** | T8–T10 | `02_domain-model`, `04_state-machines`, `05_database`, `13_configuration`, `06_mutations` §4.1–4.3 |
| **Games, results, stats** | T11–T14 | `06_mutations`, `07_statistics`, `08_game-results`, `10_scheduling` §3+§6, `03_source-of-truth` |
| **Live tracker** | T15–T17 | `07_statistics` §5, `16_security` §2, `15_api` §5, `04_state-machines` |
| **Standings** | T18–T19 | `09_standings`, `03_source-of-truth`, `13_configuration` §5 |
| **Playoffs** | T20–T22 | `11_playoffs`, `09_standings` §4, `04_state-machines`, `05_database` |
| **Registration** | T23–T25 | `12_registration`, `16_security` §7, `02_domain-model`, `04_state-machines` |
| **Bulk scheduling** | T26–T27 | `10_scheduling`, `06_mutations` §5 |
| **Read surfaces** | T28–T30 | `15_api`, `16_security`, `09_standings`, `07_statistics` |
| **Acceptance** | T31 | `19_acceptance`, `18_testing`, and every engine document |

### Not in any builder feed

| Document | Why |
|---|---|
| `23_verification-handoff` | Written for the verifier. Feeding it to a builder creates role confusion — it instructs the reader to attack the code, not write it |
| `14_import-migration` | Phase 2. Deferred by decision (D1); nothing in T1–T31 depends on it |
| `00_README` | Orientation. Read once, by a person, not per task |

### Load once, at the start

`01_principles.md` — the constitution. Twenty-five rules, each with its origin.
Not per-task material, but a builder who has never read it will re-derive its
conclusions the expensive way.

**A note on trimming further.** These feeds were sized against the real risk,
which is not context cost — it is a builder inventing a value or deleting a
constraint whose reason it could not see. When in doubt, load `20` and `22`
and trim something else.

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
