# 01 — Architecture Principles

The 28 constitutional rules, restated as things a builder can implement and a
test can check. A principle that cannot be tested is a slogan; each rule below
names its enforcement point and its acceptance test.

Every rule carries the evidence that produced it. **A rule without its scar gets
argued away by the next engineer who finds it inconvenient.**

---

## The governing sentence

> One authoritative fact → one mutation authority → explicit derivation →
> enforced invariants → adversarial verification.

---

## A. Authority

### A1 — One authoritative source per operational fact
**REQUIREMENT.** Every fact has exactly one durable home. A second writable
representation of the same fact is a defect, not an optimisation.

**Evidence (FACT):** the legacy system held season active-ness in both
`seasons.status` and `seasons.is_active` — 16 query sites read one, 5 read the
other, and nothing kept them consistent. The previous season stayed `is_active=1`
forever, leaking two "active" seasons onto public pages.

**Enforcement:** schema. If a fact has one home, there is no second column to
disagree with.
**Test:** for each fact in `03_source-of-truth.md`, a test asserts that no other
table or column can express it.

### A2 — One canonical mutation authority per fact
**REQUIREMENT.** All interfaces route through one domain command. API, admin UI,
import and tooling are callers, never independent implementations.

**Evidence (FACT):** three legacy routes wrote a game score with unequal
validation — `PATCH /api/admin/scores/:gameId` had **0** validation checks while
`POST /api/admin/games/complete` and `PUT /api/admin/games/:id/score` had 4 each.
The weakest path could set an arbitrary score on a locked game.

**Enforcement:** service layer; no route may issue its own `UPDATE` to an
authoritative column.
**Test:** every mutation route is exercised with an invalid payload; all must
reject identically.

### A3 — Derived state is a projection, never a competing authority
**REQUIREMENT.** Derived values may be cached. A cache has exactly one writer:
the derivation. Nothing else writes it, ever.

**Evidence (FACT):** `teams.wins/losses` was both incremented by four routes and
treated as truth. Reversing a completed game left its win counted forever;
re-completing added a second win. Separately, `players.season_*` (8 columns) and
`players.games_played` are written on every stat save and **read by nothing** —
3 players already disagree with their own stat lines.

**Enforcement:** service layer; the cache-writing function is the only caller of
those `UPDATE`s.
**Test:** recomputation equality (see D1).

### A4 — Every derivation has explicit dependencies and a recomputation path
**REQUIREMENT.** For each derived value the specification names its inputs, what
invalidates it, and the function that rebuilds it from authority alone.

**Evidence (FACT):** saving a box score in the legacy system does not recompute
standings and does not derive a game score. Game 1971 holds 5 real stat lines and
still reads `scheduled 0-0`. That is a missing edge in the derivation graph, not
a missing feature.

### A5 — Derived state must be reconstructible from authoritative state
**REQUIREMENT.** Deleting every derived row and rebuilding must produce identical
results. If it cannot, something derived is secretly authoritative.

**Test:** truncate projections, recompute, compare byte-for-byte.

---

## B. Integrity

### B1 — Reject illegal states at the strongest practical layer
**REQUIREMENT.** Prefer database constraints. Use the service layer only where
the rule needs context the database does not have.

**Evidence (FACT) — the most instructive failure in the project.** The legacy
code wrote `status='completed'` but ~45 sites compared against `'final'`. Every
comparison was permanently false, silently: it is why `player_game_stats` was
empty for the life of the app.

`games.status` had a `CHECK` constraint, so the bad write **failed loudly**.
`playoff_games.status` had **no constraint** and **drifted silently for months**.
Same bug, same day, opposite outcomes — decided entirely by whether the schema
was allowed to say no.

**This rule is not a preference. It is the difference between a bug found in
seconds and one found in months.**

### B2 — Prefer `state = f(authoritative inputs)` over accumulated deltas
**REQUIREMENT.** Compute from inputs. Do not add and subtract.
**Evidence (FACT):** see A3. Incremental standings drifted in two reachable ways,
both reproduced live.

### B3 — Lifecycle state is explicit state-machine state
**REQUIREMENT.** No lifecycle inferred from the presence or absence of an
unrelated field, or from a label.

**Evidence (FACT):** legacy bracket progression is inferred from round names.
`playoff_games` has **no** `next_game_id`, `winner_id`, `seed`, or
`bracket_position` column — the tournament tree exists only in the reader's head.

### B4 — Identity is stable; names are attributes
**REQUIREMENT.** Internal IDs are immutable and never reused. Names never act as
a key, join condition, or match criterion for identity.

**Evidence (FACT):** the legacy importer keyed players by name. K-Town Warriors
field two players both called "0". They merged into one record, and because the
stat upsert keys on `(player_id, game_id)`, the second person's line **overwrote**
the first in every shared game — 17 and 4 points became 7.

**The multiplier:** upsert-on-identity turns an identity error into silent data
destruction. This rule is a data-loss control, not a modelling preference.

### B5 — Stable external references are preserved
**REQUIREMENT.** Where an external system has a stable id, store it in a
dedicated column with a uniqueness constraint. Never re-derive the mapping.

**Evidence (FACT):** adding `games.external_ref` and `players.external_ref` is
what made the importer safe. Before it, identity was re-derived by name on every
run and a second run remapped people — one person's 4 games became two records
holding 4 and 5 lines.

---

## C. Mutation

### C1 — Every mutation has explicit scope and bounded blast radius
**REQUIREMENT.** A command declares what it may change. Anything outside that set
is untouched, and the transaction verifies it.

**Evidence (FACT):** schedule regeneration ran unconditional
`DELETE FROM games WHERE season_id = ?`. Four tables CASCADE off `games`, so it
destroyed a completed game and its entire box score. Reproduced as real data
loss, not theorised.

**Legacy control worth keeping (PRESERVE):** the legacy system later added a
guard returning **409** when any game in the season is not `scheduled`. GBL found
this risk independently. The concept carries forward; the all-or-nothing
granularity does not.

### C2 — Multi-write domain mutations are atomic
**REQUIREMENT.** Complete commit or complete rollback. Never partial.
**Test:** fault injection at each write boundary.

### C3 — Retryable mutations are idempotent
**REQUIREMENT.** Executing a command twice leaves the same state as once.
**Evidence (FACT):** the rewritten importer is idempotent — a second run over the
same data changed nothing (71 games / 809 lines before and after). This is
achievable and is the standard.

### C4 — Correction and downstream propagation are first-class
**REQUIREMENT.** Corrections are designed operations with defined propagation,
not an afterthought bolted onto create.

**Evidence (FACT):** the legacy bracket has **zero** write routes — no create,
seed, advance, score or correct. Correction semantics cannot be "added later" to
a path that does not exist.

### C5 — Historical gameplay data is protected from destructive deletion
**REQUIREMENT.** Anything carrying recorded gameplay is soft-deleted or archived,
never hard-deleted. Deletion of a container must not silently destroy the history
inside it.

**Evidence (FACT):** legacy player delete was a hard `DELETE`, and
`player_game_stats` CASCADEs on `player_id` — removing a player erased their
lines on games they actually played, altering other players' and teams'
historical records.

---

## D. Import and reconciliation

### D1 — Imports reconcile; they never wipe and reload
**REQUIREMENT.** An import compares, classifies and applies. It does not clear a
scope and rebuild it.

**Evidence (FACT):** the legacy importer's stated precondition was that the
season's games be deleted first. Syncing one new result meant deleting all 54
games.

### D2 — Stable external IDs are used for matching
**REQUIREMENT.** Match on external id. Fall back to attributes only for a
one-time adoption of pre-existing records, and record the result permanently.

### D3 — Imports report what they changed
**REQUIREMENT.** Every run reports created, updated, unchanged, skipped and
unresolved. Silence is not success.

### D4 — Imports are resumable and replay-safe
**REQUIREMENT.** A replay of an already-imported dataset produces no changes.

**Evidence (FACT):** the source system mutates history — RecLeague deleted player
ids mid-season, orphaning 8 stat lines that were legitimately earned, and
re-paired 3 of 8 fixtures on one date. **An import must tolerate an upstream that
rewrites its own past.**

---

## E. Deployment and operations

### E1 — Code/schema compatibility is mechanically gated before deployment
**REQUIREMENT.** Code requiring a schema change cannot reach an environment
lacking it. Enforced by a machine, not a checklist.

**Evidence (FACT) — this failure is real, twice, not hypothetical.** Column reads
were shipped ahead of their migrations. The first outage took down the admin
schedule; the second took down public leaderboards and standings **while the
league owner was entering live statistics.** Both times the local check passed,
because locally the column already existed.

### E2 — Mutating tooling is physically isolated from production
**REQUIREMENT.** Separate database, separate credentials, plus a runtime refusal
check. Logical separation inside one database is insufficient.

**Evidence (FACT):** the legacy E2E suite used real Season 3 teams. It
accumulated 19 phantom results, inflating one team to a fake 17-0, and season
creation *reassigns* team ids — so the suite was draining real teams out of the
live season on every run. Separately, `bootstrap-admin.cjs` still writes to the
real database.

### E3 — Operational health and failure are observable
**REQUIREMENT.** Failures surface as alerts, not as a user noticing a blank page.
**Evidence (FACT):** the legacy dev server died unattended six or more times
during one working period, including mid-handoff.

---

## F. Verification

### F1 — Important invariants are automated
**REQUIREMENT.** Each invariant in this specification has a named automated test.

### F2 — Verification is tested by deliberate failure
**REQUIREMENT.** Every check must be shown to fail when it should. A check only
ever run against a passing case is unproven.

**Evidence (FACT) — the check itself was the broken thing, repeatedly.** A backup
script reported success on a garbage snapshot: its row-count loop skipped tables
it could not read, so a table-less database skipped every check, and its content
comparison compared two empty strings and called that a match. It was found only
by deliberately feeding it a corrupt database.

**Also FACT:** a CI pipeline dry-run passed locally and failed remotely in six
seconds — it had been run from a directory where the path it assumed existed. A
62-site audit was reported complete at 45 sites. A figure of "217/217 matching"
circulated for days and was never reproducible from any committed script.

### F3 — Idempotency is tested by replay
### F4 — Atomicity is tested with fault injection
### F5 — Derived state is tested against independent recomputation
**REQUIREMENT.** The test recomputes from authority by a separate path and
compares. Not by calling the same function twice.

---

## G. Representational design

### G1 — Prefer making an error unrepresentable over validating against it
**RECOMMENDATION — proposed as a new rule; not yet ratified.**

> **Naming note.** Rule IDs in *this* document are section-letter based (`A1`,
> `B4`, `F3`, `G1`). The `G*` identifiers in `20_decisions.md` are **governance
> gates** and are a different series — cited everywhere as **"Gate G1"**. Rule
> G1 below is not Gate G1.

Where a domain error can be designed out of the data model, do that rather than
adding a validation rule that must be remembered.

**Evidence (FACT):** legacy stat entry asked for FGM, which silently includes
three-pointers. A scorekeeper entering "3 twos and 2 threes" as FGM=3, 3PM=2
produced **8 points instead of 12**. Separately, validation required FGA — a
statistic this league does not collect — so `0` was read as "zero attempts"
rather than "not tracked", and **every real stat line was rejected**.

The fix that worked was not better validation. It was collecting 2PM and 3PM and
**deriving** FGM and points, which makes the error impossible to express.

**Status:** RECOMMENDATION. Ratifying this as a constitutional rule is a decision
for the architecture owner. It is applied in `07_statistics.md` regardless,
because the evidence for that specific case is direct.

---

## How these rules are used

Each engine specification cites the rules it implements. The traceability matrix
(`22_traceability.md`) carries every rule from evidence through to acceptance
test. If a requirement in this specification cannot be traced to a rule and a
piece of evidence, it is a RECOMMENDATION and must be labelled one.
