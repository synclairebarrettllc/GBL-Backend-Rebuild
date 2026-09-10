# 21 — Implementation Order

**Status: the plan of record.** G3 is DECIDED — this sequence, decomposed into
**T1–T31** in `24_build-tasks.md`, *is* the build inventory (`20_decisions.md`).
The order is dependency order, not preference; resequencing is cheap but the
dependencies are real.

This document explains **why** the stages fall in this order. `24_build-tasks.md`
is what you actually work from.

---

## 1. Scope reset — what is and is not a prerequisite

**Settled.** The following are **not** prerequisites for this rebuild:

| Item | Status |
|---|---|
| Legacy data migration | **Phase 2** (D1, deferred) |
| Season 3 resolution | **Phase 2** |
| RecLeague / Reckly integration | **Phase 2** (also O10) |

**In scope and core:** live courtside stat tracking (S3), registration (S10),
scheduling with bulk operations (S17), standings, playoffs.

**Why this matters to the order.** The rebuild does not have to carry historical
data forward before it can be useful. It has to run a season correctly. That
removes the largest source of sequencing risk from the critical path.

---

## 2. Ordering principles

1. **Dependency order, not value order.** A piece is built after everything it
   derives from.
2. **Each piece ends verifiable.** Every stage closes with tests that pass and
   evidence attached (`19_acceptance.md` §1).
3. **Guards before the things they guard.** Build the gate before the code that
   needs gating — both production outages happened because the guard came after.
4. **One task = one branch = one PR** (S27) throughout.
5. **Build the riskiest unknown early enough to be wrong about it.** The live
   tracker has no legacy precedent; discovering its constraints in the final
   stage would be the worst possible timing.

---

## 3. The sequence

### Stage 0 — Rails

Everything in `17_operations.md` §3, before any domain code.

- Repository, branch protection, `main` protected
- CI (S29), migration guard wired to `prebuild`, tracked pre-push hook
- Verified backup script, **including its known-bad-database test**
- Secret scanning
- Static checks from `18_testing.md` §3 — **as CI steps, empty codebase or not**

**Exit criterion.** Every gate has **refused something**. A gate that has never
said no is untested.

**Why first.** These are cheap now and expensive later, and their absence is the
documented root cause of the only two production incidents this project has had.

---

### Stage 1 — Schema and identity

- Full DDL from `05_database.md`, including every `CHECK`, partial unique index
  and `RESTRICT`
- `IdentityService`: Person, Player, external refs
- `SeasonService`, `TeamService`, `RosterService`, `VenueService`
- `ConfigService` with schema validation

**Exit criteria.** `season.single-active` is enforced **by the database**.
`identity.one-per-season` holds. A season cannot activate with an incomplete
config, and the rejection names the missing keys.

**Why here.** Every later piece writes rows that reference these. Constraints
added after data exists are constraints that get relaxed to fit the data.

---

### Stage 2 — Games, results, statistics

- `ScheduleService` — individual operations only
- `StatsService` with the 2PM/3PM representation and nullable attempts
- `GameResultService` as **sole score authority**
- **The derivation edge**: stat write → score, same transaction

**Exit criteria.** `stats.scoring-arithmetic` passes (12, not 8).
`stats.makes-only-line-accepted` passes. `stats.derivation-edge` passes — the
game-1971 defect is structurally impossible.

**Why here, and why it is the heart of the build.** This is where the legacy
system's central failure lived. Everything downstream reads what this stage
produces.

---

### Stage 3 — The live tracker

- Per-game capability tokens (`16_security.md` §2)
- Progressive persistence; idempotent writes
- Real-time propagation
- Interruption and retry behaviour

**Exit criteria.** Tracker scope, expiry and escalation tests pass.
`tracker.progressive-save` passes with a real interruption.

**Why this early.** It is the piece with **no legacy precedent** and the most
product risk. It is also the one the league actually asked for. Building it in
stage 3 means its constraints are known while there is still room to respond to
them.

---

### Stage 4 — Standings

- `StandingsService` as a pure projection — no mutations
- Tiebreak criterion vocabulary; configurable chains (S20)
- Config-version stamping

**Exit criteria.** `standings.recompute-equality`, `standings.deterministic`, and
**`standings.correction-reverses`** all pass. A multi-team tie resolves by the
configured strategy and the output names it (O3 default: `sub_table_restart`).

---

### Stage 5 — Playoffs

- `PlayoffService`: seeds with `basis_snapshot`
- `BracketService`: structural progression via FK edges
- Bounded correction propagation

**Exit criteria.** `bracket.structural-progression` passes — rename every round
label, nothing changes. `bracket.correction-bounded` passes.

---

### Stage 6 — Registration

- Public submission, idempotent and progressively saved
- Acceptance with **operator-confirmed** identity matching
- Age verification against `age_as_of_date`; guardian rule
- Waiver slot (O11)
- PII isolation

**Exit criteria.** No public or AI-surface response contains a registration
field. `registration.no-auto-match` passes.

**Why late.** It depends on identity, seasons and rosters, and it does not block
running a season with a roster loaded by an admin.

---

### Stage 7 — Bulk scheduling

- Schedule generation as a dry run (S21)
- `bulkReschedule` — atomic, dry run by default (S17)
- Change-set emission for the G4 notification decision

**Exit criteria.** `schedule.bulk-atomic` passes under fault injection.
`schedule.bulk-reports-all-conflicts` passes.

**Why after individual operations.** Bulk operations are compositions. Composing
unproven primitives multiplies their defects.

---

### Stage 8 — Read surfaces and dashboard

- Public API with deleted-row filtering **in the data access layer**
- Admin dashboard flagging incomplete state (S26)
- AI read-only surface (S12)

**Exit criteria.** `api.deleted-filtered-everywhere` passes by construction, not
by audit. A played game missing stats appears on the dashboard.

---

### Stage 9 — Acceptance

The full-season scenario (`19_acceptance.md` §2), automated, in CI.

---

### Phase 2 — Deferred

Migration and reconciliation (`14_import-migration.md`), Season 3 resolution,
RecLeague/Reckly integration. Undeferred by decision, not by drift.

---

## 4. Which decision each stage consumes

**Nothing here is open.** Every item has a value in `20_decisions.md` Part 2 —
DECIDED (technical) or DEFAULT (league policy, changeable at a stated cost). This
table says **when each value first matters**, so a change arriving later is
recognised as rework rather than a surprise.

**`20_decisions.md` is the only home for these values. This table does not restate
them** — it points. If you want to know what the forfeit rule *is*, read the
register, not this page.

| Decision | First consumed at | Class |
|---|---|---|
| **G2** — principles as new-build law | Stage 1 | DECIDED |
| **G3** — build inventory = the task queue | Stage 1 | DECIDED |
| **O7** — platform | Stage 1 | DECIDED |
| **O9** — timezone semantics | Stage 2 | DECIDED |
| **O5** — stat-to-score discrepancy | Stage 2 | DEFAULT |
| **O1** — composite formulas | Stage 2 | DEFAULT |
| **O2** — forfeits | Stage 4 | DEFAULT |
| **O3** — multi-team ties | Stage 4 | DEFAULT |
| **O12** — config retroactivity | Stage 4 | DECIDED |
| **O4** — seed durability | Stage 5 | DEFAULT |
| **O6** — roster eligibility | Stage 6 | DEFAULT |
| **O11** — waiver vendor | Stage 6 | DEFAULT + legal constraint |
| **O8** — scheduling objectives | Stage 7 | DEFAULT |
| **G4** — notifications | Stage 7 | DEFAULT |
| **O10** — Reckly vs recleague | Phase 2 | OPEN-FACT — blocks nothing |

### Cost of a late change

Most DEFAULTs are a config edit plus a recompute, because standings, totals and
rankings are **projections** — nothing is stranded. The exceptions, worth
reviewing before their stage rather than after:

| Decision | Why a late change hurts |
|---|---|
| **O7** platform | Schema dialect and real-time transport depend on it |
| **O9** timezone | A representation decision baked into every stored instant |
| **O6** `multi_team_allowed` | Changing it after rosters exist means reconciling players who already appear twice |
| **O2** forfeit score | Feeds point differential, the default first tiebreak |

---

## 5. What not to do

| Anti-pattern | Why |
|---|---|
| Build the UI first and infer the domain from it | A UI control is not evidence an operation exists (FACT) |
| Defer constraints until "the data settles" | Constraints added late get relaxed to fit bad data |
| Build bulk operations before individual ones | Composition multiplies defects |
| Ship a read that depends on an unapplied migration | Both production outages, exactly (FACT) |
| Substitute your own value for a stated one | Converts a league decision into a silent default |
| Leave the guards for the end | They are the cheapest thing in Stage 0 and the most expensive omission |
