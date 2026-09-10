# 06 — Mutation Contracts

Every write in the system, stated as a contract. If an operation is not in this
document, **it does not exist** — there is no "and also whatever the route needs
to do."

**Evidence for why this document exists (FACT).** The legacy system had three
separate routes writing `game.home_score`, carrying 0, 4 and 4 validation checks
respectively. Which rules applied to a score depended entirely on which URL the
caller happened to hit. That is not a bug in one route; it is the absence of a
mutation contract.

---

## 1. The universal form

Every mutation is specified with these fields. A contract missing any of them is
incomplete.

| Field | Meaning |
|---|---|
| **Operation** | `Service.method` — the canonical name |
| **Authority** | Which fact(s) from `03_source-of-truth.md` this write owns |
| **Actor** | Who may invoke it (see `16_security.md`) |
| **Preconditions** | Checked **inside** the transaction |
| **Effect** | The authoritative rows written |
| **Cascade** | Derived state recomputed, and in which transaction |
| **Idempotency** | Replay behaviour |
| **Failure** | What is left behind when it fails |

---

## 2. Universal rules

These apply to every contract below without restatement.

**R1 — One authority per fact.** A mutation writes only the facts its Authority
line claims. Writing another service's fact is a defect even when convenient and
even when correct.

**R2 — Validation is inside the transaction.** Preconditions are checked and the
write performed in one transaction. Read-then-write across two statements is a
race.

**Evidence (FACT):** the legacy score-update path checked game status, then
updated, with a source comment acknowledging the gap.

**R3 — No silent no-ops.** A mutation either changes state or returns a typed
error. Returning success for a write that did nothing is prohibited.

**Evidence (FACT):** the admin delete button had no handler. It looked identical
to success for months. Nobody could tell, because nothing said no.

**R4 — Typed errors.** Failures carry a machine-readable code, the entity, the
current state, the attempted state, and a human sentence. `500` with a stack
trace is not a contract.

**R5 — Routes do not mutate.** No route, script, cron, or CLI tool issues
`INSERT`/`UPDATE`/`DELETE` against a domain table. They call services. This
includes import scripts and one-off fixes.

**Evidence (FACT):** the recleague importer wrote directly, which is precisely
why it double-counted players and had to be given identity and provenance rules
retroactively.

**R6 — Idempotency.** Every mutation accepts an optional client-generated
`operation_id`. A repeat with the same id returns the original outcome and
changes nothing. Required for the live tracker (`07_statistics.md`); available
everywhere.

**R7 — Bounded blast radius.** A mutation's cascade is enumerated in its
contract. Anything not listed is byte-identical afterward. This is tested, not
assumed.

**R8 — Failure leaves no partial state.** A failed mutation rolls back
completely. There is no "wrote the game but not the result" outcome.

**Evidence (FACT):** deleting an admin orphaned 24 `admin_logs` rows because
SQLite's CLI has `foreign_keys` off by default — a partial effect that looked
like a complete one. **REQUIREMENT:** `PRAGMA foreign_keys = ON` is asserted at
connection open and tested, not assumed.

---

## 3. Service inventory

| Service | Owns |
|---|---|
| `IdentityService` | Person, Player, identity linking |
| `TeamService` | Team |
| `RosterService` | RosterMembership |
| `SeasonService` | Season, Division lifecycle |
| `ScheduleService` | Game scheduling facts (when, where) |
| `StatsService` | PlayerGameStatLine |
| `GameResultService` | GameResult — **sole score authority** |
| `PlayoffService` | PlayoffSeed |
| `BracketService` | Bracket, BracketMatch |
| `RegistrationService` | Registration |
| `ConfigService` | Season configuration |
| `VenueService` | Venue |

**StandingsService has no mutations.** It is a pure projection
(`09_standings.md`). If a method on it ever writes, the architecture has been
violated.

---

## 4. Contracts

### 4.1 IdentityService

#### `createPerson(attributes)`
- **Authority:** Person identity
- **Actor:** admin; RegistrationService (internal)
- **Preconditions:** required attributes present
- **Effect:** one `person` row
- **Cascade:** none
- **Idempotency:** by `operation_id`
- **Failure:** no row

#### `createPlayerForSeason(person_id, season_id, attributes)`
- **Authority:** Player identity
- **Preconditions:** person exists; season is `draft` or `active`; no existing player for `(person_id, season_id)`
- **Effect:** one `player` row
- **Cascade:** none — a new Player has no history to recompute
- **Failure:** unique violation returns `PLAYER_EXISTS_FOR_SEASON` with the existing id

#### `linkPlayerToPerson(player_id, person_id)`
- **Preconditions:** **operator-confirmed.** Never invoked automatically.
- **Effect:** sets `player.person_id`
- **Cascade:** career projections recompute (they are projections; nothing stored changes)

**REQUIREMENT — no automatic identity merge.** The system may *suggest* that two
records are the same human. It may not act on that suggestion.

**Evidence (FACT):** name-based identity re-derivation created two records for
one person (4 and 5 stat lines across their 4 games) and invented a third
player. The fix was a stable `external_ref` plus operator confirmation.

#### `setExternalRef(entity, id, external_ref)`
- **Authority:** external identity mapping
- **Preconditions:** `external_ref` not already claimed within its namespace
- **Effect:** sets the ref
- **Cascade:** none
- **REQUIREMENT:** external refs are **assigned once**. Reassigning one silently
  re-points history and is prohibited; changing one is a delete plus an assign,
  both audited by effect.

---

### 4.2 RosterService

#### `addMembership(player_id, team_id, effective_from)`
- **Preconditions:** player and team in the **same season**; no conflicting open membership per **O6**
- **Effect:** one `roster_membership` row
- **Cascade:** none — **stat lines are never touched by roster changes**
- **Failure:** typed error naming the conflicting membership

#### `endMembership(membership_id, effective_to)`
- **Preconditions:** membership open; `effective_to >= effective_from`
- **Effect:** sets `effective_to`
- **Cascade:** **none**

**REQUIREMENT.** Ending a membership never deletes, hides, or reassigns stat
lines. A player who left mid-season keeps every game they played, attributed to
the team they played it for. The stat line carries its own `team_id` precisely so
this is true.

#### `transferPlayer(player_id, from_team, to_team, effective_at)`
- **Effect:** ends one membership and opens another, **one transaction**
- **Cascade:** none
- **Failure:** neither membership changes

---

### 4.3 SeasonService

#### `activateSeason(season_id)`
- **Preconditions:** status `draft`; config passes schema validation; **no other active season in the league**
- **Effect:** `status = 'active'`; any previously active season → `completed`
- **Cascade:** "current season" resolves to this season everywhere — because every
  read derives it from `status`, not from a second flag
- **Enforcement:** the partial unique index makes a second active season
  **impossible at the database level**, not merely unlikely

**Evidence (FACT):** legacy carried `status` *and* `is_active`, queried at 16 and
5 sites respectively, and ended with two seasons active at once.

#### `closeSeason(season_id)`
- **Preconditions:** every game is `finalized`, `cancelled` or `forfeited`
- **Effect:** `status = 'completed'`
- **Cascade:** standings frozen; awards computable
- **Failure:** returns the list of unresolved games — **not a count**

**REQUIREMENT.** An error that blocks on unfinished work names the work.
"3 games remain" sends the operator hunting; the list ends the search.

---

### 4.4 ScheduleService

#### `scheduleGame(season_id, home_team, away_team, starts_at, venue_id, court)`
- **Authority:** `game.starts_at`, `venue_id`, `court`
- **Preconditions:** both teams in the season; teams differ; slot free (database unique index, S22); venue exists
- **Effect:** one `game` row, `status = 'scheduled'`
- **Cascade:** none
- **Failure:** slot conflict returns `VENUE_SLOT_TAKEN` **with the conflicting game id**

#### `rescheduleGame(game_id, starts_at, venue_id, court)`
- **Preconditions:** game not `finalized`; new slot free
- **Effect:** updates scheduling facts only
- **Cascade:** none — **rescheduling never touches results or stats**

#### `cancelGame(game_id, reason)`
- **Preconditions:** game not `finalized`
- **Effect:** `status = 'cancelled'`
- **Cascade:** standings recomputed (the game leaves the denominator)

#### `deleteGame(game_id)` — soft delete
- **Preconditions:** game has **no stat lines**; not `finalized`
- **Effect:** sets `deleted_at`
- **Cascade:** removed from every read; standings recomputed
- **REQUIREMENT:** if the game has stat lines, the mutation **fails** and directs
  the operator to `cancelGame` or to delete the lines explicitly first.

**Evidence (FACT):** a delete path that destroys history silently is how a
season's box scores disappear. The three-state delete built in the legacy system
(not found / has stats / deleted) exists because the alternative was discovered
the hard way. `deleted_at` also means the importer can distinguish *deliberately
deleted* from *missing*, and decline to resurrect it.

---

### 4.5 StatsService

#### `upsertStatLine(game_id, player_id, team_id, stats, operation_id)`
- **Authority:** PlayerGameStatLine
- **Actor:** admin, or a **tracker token scoped to this game**
- **Preconditions:**
  - game exists, not deleted, not `finalized` (unless a correction)
  - player has a roster membership on `team_id`, **or** the call declares a fill-in
  - counting stats ≥ 0; `made <= attempted` where attempted is present
- **Effect:** insert or update one `player_game_stat_line`
- **Cascade — same transaction:**
  1. if `game_result.result_source = 'derived'`, recompute both scores
  2. if the game is `in_progress` or later, leave status alone; if `scheduled`,
     transition to `in_progress`
  3. if the game is `finalized`, recompute standings and re-evaluate any bracket
     match
- **Idempotency:** replaying `operation_id` returns the current line unchanged
- **Failure:** the line is unchanged **and** the score is unchanged

**REQUIREMENT — the cascade is the point.** A stat write that does not recompute
the derived score is not a partial implementation; it is the legacy bug.

**Evidence (FACT):** game 1971 holds five real stat lines entered by the league
owner and still reads `scheduled 0-0`.

#### `deleteStatLine(game_id, player_id)`
- **Preconditions:** game not `finalized` unless a correction
- **Effect:** row removed (hard delete — stat lines have no lifecycle,
  `04_state-machines.md`)
- **Cascade:** identical to `upsertStatLine`, same transaction

---

### 4.6 GameResultService

**Sole authority for scores. No other service and no route writes a score.**

#### `enterResult(game_id, home_score, away_score)`
- **Preconditions:** game not deleted; **no stat lines exist for the game**
- **Effect:** `game_result` with `result_source = 'entered'`; game → `completed`
- **Cascade:** standings recomputed
- **Failure:** rejected with `RESULT_WOULD_CONTRADICT_STATS` if lines exist

**REQUIREMENT — ADR-010.** Where a result is designated `derived`, the score is a
projection of authoritative stat lines and direct score overwrite is refused.
Authority is established by the `result_source` state, not by a general
precedence rule between entry methods (`08_game-results.md` §2).

**REQUIREMENT — import precedence.** A separate rule: an import never overwrites
a locally authored result, whether `derived` or `entered`.

**Evidence (FACT), verified in the legacy repository (`GBL-DOT-COM`):**
migration 0029 defines
`games.score_source` with a CHECK constraint; the importer guard at
`scripts/import-recleague.cjs:409-420` skips games marked `live` and logs both
values on disagreement; the write paths default to `'live'` so an undeclared
caller fails safe. `score_source` is the ancestor of `result_source`.

#### `recomputeDerivedResult(game_id)` — internal
- **Actor:** StatsService only. Not exposed.
- **Effect:** sets scores from the sum of stat lines
- **Cascade:** standings; bracket match if applicable

**REQUIREMENT.** A `derived` result is **never** editable directly. Correct the
stat lines. An endpoint that lets an operator type over a derived score
reintroduces two homes for one fact.

#### `finalizeGame(game_id)`
- **Preconditions:** game `completed`; a result exists; **UNKNOWN — O5**
  completeness rule
- **Effect:** game → `finalized`; result → `final`
- **Cascade:** standings recomputed; seed eligibility opens
- **Failure:** unchanged

#### `correctFinalizedGame(game_id, reason)`
- **Preconditions:** game `finalized`
- **Effect:** game → `completed`; result → `provisional`
- **Cascade — enumerated:** standings recomputed; any bracket match containing
  this game re-evaluated; propagation follows `winner_advances_to` edges **only**
- **REQUIREMENT:** matches not reachable along those edges are byte-identical
  afterward (`bracket.correction-bounded`)

**REQUIREMENT.** Correction is a **first-class, named operation** — not a reopen
flag, not an admin override, not a direct `UPDATE`. It is expected to happen and
is specified accordingly.

**Evidence (FACT):** legacy had a `reopen` route that set `in_progress`, cleared
the lock, and defined no propagation at all.

---

### 4.7 PlayoffService

#### `finalizeSeeds(season_id)`
- **Preconditions:** regular season games all resolved; seeding rules configured (**UNKNOWN — O3**)
- **Effect:** `playoff_seed` rows with `finalized_at` and **`basis_snapshot`** — the standings rows used
- **Cascade:** bracket becomes generatable
- **REQUIREMENT:** the snapshot is written in the same transaction as the seeds.
  A seed without its basis cannot be explained to a team six weeks later.

#### `reseed(season_id)` — behaviour is **UNKNOWN — O4**
- The operation is specified; its *legality after finalisation* is policy.
- All three candidate policies (durable / reseed / snapshot-based) are
  implementable against this schema without change.

---

### 4.8 BracketService

#### `generateBracket(season_id, format)`
- **Preconditions:** seeds finalised; format valid for the seed count
- **Effect:** `bracket` (`draft`) plus **every** `bracket_match`, including all
  `winner_advances_to_match_id` edges
- **REQUIREMENT:** the structure is complete before the bracket may be `seeded`.
  A partially built bracket is not seedable — this is what makes
  progression-by-round-name impossible.

**Evidence (FACT):** legacy inferred progression from round labels; correcting it
required changes at 24 sites.

#### `recordMatchResult(match_id)` — internal, triggered by game finalisation
- **Effect:** evaluates the series per config; sets winner when decided
- **Cascade:** fills the downstream match's participant slot **along the edge**;
  that match transitions `pending → ready` when both slots resolve
- **REQUIREMENT:** propagation is one hop per transaction and follows FKs. No
  service scans for "the next round".

---

### 4.9 RegistrationService

#### `submitRegistration(payload)`
- **Actor:** public
- **Preconditions:** required fields; waiver accepted; age per S10
- **Effect:** `registration` row, `status = 'submitted'`
- **Cascade:** none
- **REQUIREMENT:** submission creates **no** Person and **no** Player. A form
  submission is not an identity.

#### `acceptRegistration(registration_id, person_id?)`
- **Actor:** admin
- **Preconditions:** status `submitted`
- **Effect:** status → `accepted`; links to an existing Person **only if the
  operator supplied one**
- **REQUIREMENT:** no automatic name matching (B4).

#### `assignToTeam(registration_id, team_id)`
- **Preconditions:** status `accepted`; team under capacity per config
- **Effect — one transaction:** Person created or matched; Player created for the
  season; RosterMembership opened; registration → `assigned`
- **Failure:** none of the four rows exist

---

### 4.10 ConfigService

#### `updateSeasonConfig(season_id, config)`
- **Preconditions:** config passes schema validation; season not `archived`
- **Effect:** replaces `season.config`
- **Cascade:** **UNKNOWN — O12.** Whether changing a tiebreak chain mid-season
  retroactively re-ranks completed weeks is policy, not engineering.
- **REQUIREMENT:** every config write is versioned so that a standings table can
  state which config produced it.

---

## 5. Bulk and dangerous operations

**REQUIREMENT.** Any operation touching more than one game's worth of data is a
**named mutation with a contract**, not a script.

| Operation | Requirement |
|---|---|
| Import a dataset | Idempotent; replay is a no-op; respects `deleted_at`; never overwrites a live-entered result |
| Recompute all standings | Pure; produces identical output on repeat |
| Rebuild all projections | Supported and tested (`reconstruction.full-rebuild`) |
| Delete a season | **Prohibited.** `RESTRICT` at the database level |

**REQUIREMENT — every dangerous operation has a dry run.** A mode that reports
exactly what would change, changes nothing, and is the default for a first
invocation.

**Evidence (FACT):** a verified backup refused to keep a corrupt snapshot only
because it checked its own work afterward. Nothing else in the system did.

---

## 6. Error model

```
{
  code:        'GAME_NOT_FOUND' | 'ILLEGAL_TRANSITION' | 'VENUE_SLOT_TAKEN' | ...
  entity:      'game',
  entity_id:   1971,
  current:     'finalized',
  attempted:   'in_progress',
  message:     'Game 1971 is finalized. Use correctFinalizedGame.',
  details:     { ... }
}
```

**REQUIREMENT.** The message names the operation that *would* work. An error that
only says no makes the operator guess, and guessing at an admin console is how
data gets damaged.

**REQUIREMENT.** No mutation returns `200` for a rejected write. **FACT:** the
legacy importer read `game_id` off a `409` and treated it as success, then failed
downstream with "Game not found" — a confusing error two steps from its cause.

---

## 7. Acceptance tests

| Test | Asserts |
|---|---|
| `mutation.single-authority` | Static check: only GameResultService writes score columns |
| `mutation.no-route-sql` | Static check: no `INSERT`/`UPDATE`/`DELETE` outside `services/` |
| `mutation.idempotent-replay` | Every mutation, replayed with its `operation_id`, is a no-op |
| `mutation.rollback-complete` | Injected failure at each step leaves zero partial state |
| `mutation.typed-errors` | Every rejection carries code, entity, current, attempted |
| `mutation.no-silent-noop` | No mutation returns success without a state change |
| `mutation.blast-radius` | For each mutation, everything outside its cascade is byte-identical |
| `mutation.fk-enforcement` | `PRAGMA foreign_keys` is ON for every connection |
| `roster.end-preserves-stats` | Ending a membership changes no stat line |
| `result.derived-not-editable` | No path can type over a derived score |
| `result.import-precedence` | An import cannot overwrite a locally authored result |
| `schedule.delete-refuses-with-stats` | Deleting a game with stat lines fails and says why |
| `season.close-lists-blockers` | Failure names the unresolved games, not a count |
