# 21 — Implementation Order

**Status: RECOMMENDATION, pending G3.** The build-piece inventory is explicitly
**derived, not locked** (`20_decisions.md`, G3). This sequence should be ratified
before it is treated as a plan of record.

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
**`standings.correction-reverses`** all pass. Multi-team ties are **flagged**
while O3 is open.

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

## 4. What must be decided when

| Decision | Needed by | Consequence if still open |
|---|---|---|
| **G3** — build-piece inventory | **before Stage 1** | This sequence is unratified |
| **G2** — technical rules constitution | before Stage 1 | Rules apply as new-build law by default |
| **O7** — platform | before Stage 1 | DDL dialect and real-time transport unsettled |
| **O9** — timezone semantics | Stage 2 | Recommendation applies; per-day rules ambiguous |
| **O5** — finality completeness | Stage 2 | Finalisation does not check; discrepancy recorded |
| **O1** — composite formulas | Stage 2 | Metrics ship without composites |
| **O2** — forfeits | Stage 4 | Forfeited games excluded from standings |
| **O3** — multi-team ties | Stage 4 | Ties flagged unresolved-by-policy |
| **O12** — config retroactivity | Stage 4 | Version stamped; behaviour unsettled |
| **O4** — seed durability | Stage 5 | Durable, with a flagged discrepancy |
| **O6** — roster eligibility | Stage 6 | Overlaps permitted; fill-ins recorded |
| **O11** — waiver vendor | Stage 6 | Slot present, unfilled |
| **O8** — scheduling objectives | Stage 7 | Hard constraints only; balance reported |
| **G4** — notifications | Stage 7 | Change set emitted, not delivered |
| **O10** — Reckly vs recleague | Phase 2 | Source parameterised |

**The cheapest unblocks are G3 and G2** — they cost a decision, not a discovery,
and everything downstream keys off them.

---

## 5. What not to do

| Anti-pattern | Why |
|---|---|
| Build the UI first and infer the domain from it | A UI control is not evidence an operation exists (FACT) |
| Defer constraints until "the data settles" | Constraints added late get relaxed to fit bad data |
| Build bulk operations before individual ones | Composition multiplies defects |
| Ship a read that depends on an unapplied migration | Both production outages, exactly (FACT) |
| Resolve an UNKNOWN to unblock yourself | Converts a league decision into a silent default |
| Leave the guards for the end | They are the cheapest thing in Stage 0 and the most expensive omission |
