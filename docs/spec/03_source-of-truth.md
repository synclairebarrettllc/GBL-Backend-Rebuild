# 03 — Source of Truth and Derivation

Who owns each fact, who may change it, what is computed from it, and how that
computation is rebuilt.

**The test this document must pass:** for every fact, exactly one row. If two
rows claim the same fact, that is a defect in the specification, not a modelling
nuance.

---

## Authority matrix

| Fact | Authoritative store | Canonical mutation | Derived projections | Recompute path | Enforcement | Test |
|---|---|---|---|---|---|---|
| Person identity | `person.id` | IdentityService | display names, rosters | n/a — authoritative | immutable PK; no update path to `id` | `identity.immutable` |
| Player identity | `player.id` | IdentityService | season rosters, leaderboards | n/a | PK; unique `(person_id, season_id)` | `identity.one-per-season` |
| Team identity | `team.id` | TeamService | standings, schedule views | n/a | PK; **no** cross-season reassignment | `identity.no-reparent` |
| Roster membership | `roster_membership` rows | RosterService | current roster, historical roster | n/a | FK + date-range constraints | `roster.time-scoped` |
| Season currency | `season.status` | SeasonService | "current season" everywhere | n/a | **partial unique index**: ≤1 `active` per league | `season.single-active` |
| Schedule assignment | `game.starts_at`, `venue_id`, `court` | ScheduleService | calendars, team schedules | n/a | conflict constraints | `schedule.no-double-book` |
| Game result | `game_result` row | **GameResultService — sole authority** | standings, bracket progression, summaries | n/a when `entered`; from stat lines when `derived` | one service; no route writes score directly | `result.single-authority` |
| Player game stats | `player_game_stat_line` rows | StatsService | player totals, leaderboards, team stats, **derived score** | n/a — authoritative | unique `(game_id, player_id)`; non-negative checks | `stats.grain` |
| Player season totals | **none — projection** | none | leaderboards, player pages | `sum(stat lines where season)` | no writable column exists | `totals.recompute-equality` |
| Team season record | **none — projection** | none | standings table | `f(finalised results)` | no writable column exists | `standings.recompute-equality` |
| Standings order | **none — projection** | none | public + admin standings | `f(records, tiebreak chain)` | evaluator is the only producer | `standings.deterministic` |
| Playoff seed | `playoff_seed` row | PlayoffService | bracket slot resolution | frozen at finalisation + `basis_snapshot` | `finalized_at` gates mutation | `seed.durable` |
| Bracket structure | `bracket`, `bracket_match` rows | BracketService | public bracket view | n/a — authoritative | FK progression edges | `bracket.structural` |
| Bracket progression | `winner_advances_to_match_id` edge + match result | BracketService | downstream participants | replay from match results along edges | edges are FKs, not labels | `bracket.propagation` |
| Registration | `registration` row | RegistrationService | admin queue, roster assignment | n/a | state machine | `registration.lifecycle` |
| League/season config | `season.config` | ConfigService | every engine's behaviour | n/a | schema-validated JSON | `config.validated` |

---

## The rule that generates this table

**One fact, one home.** Where the table says "none — projection", **no column may
exist that stores it as an independent value.**

**Evidence (FACT).** The legacy system violated this four times:

1. `seasons.status` **and** `seasons.is_active` — 16 query sites vs 5, silently
   inconsistent, leaving two seasons "active".
2. `teams.wins/losses` as both accumulator and truth — two drift paths confirmed
   live.
3. `players.season_*` (8 columns) plus `games_played` — written on every stat
   save, read by nothing, **already disagreeing with their own stat lines on 3
   players**.
4. Three routes writing `game.home_score` with 0, 4 and 4 validation checks
   respectively.

Each is the same failure. The matrix above is the countermeasure.

---

## Caching a projection

A projection **may** be cached for read performance. If it is:

1. The cache has **exactly one writer** — the derivation function.
2. The cache is **never read as authority** by a mutation making a decision.
3. An automated test asserts `cached == freshly recomputed`.
4. Discarding the entire cache and rebuilding is a supported, tested operation.

**REQUIREMENT.** A cached projection column is annotated as such in the schema
(`05_database.md`) so a future engineer cannot mistake it for authoritative.

---

## Derivation graph

```
                    PlayerGameStatLine
                            │
                            │  (result_source = 'derived')
                            ▼
                      GameResult ◄──── direct entry (result_source = 'entered')
                            │
                 ┌──────────┴───────────┐
                 ▼                      ▼
          Team season record      Player season totals
                 │                      │
                 ▼                      ▼
          Standings order         Leaderboards
                 │
                 ▼
           PlayoffSeed  ──(frozen at finalisation, with basis_snapshot)
                 │
                 ▼
           BracketMatch slot resolution
                 │
                 ▼
          Bracket progression ──(follows winner_advances_to edges)
```

### Each edge, specified

| Edge | Trigger | Transaction | On correction |
|---|---|---|---|
| Stat lines → GameResult | stat line write, when `result_source = 'derived'` | **same transaction** as the stat write | recompute score; if it changes, cascade downward |
| GameResult → team record | result finalised, unfinalised, or changed | same transaction | recompute affected season |
| GameResult → player totals | stat line write | may be deferred (projection) | recompute on read or on schedule |
| Team record → standings order | any record change | computed on read | n/a |
| Standings → PlayoffSeed | **explicit operator action only** | seeding transaction | see O4 |
| Seed → bracket slots | bracket generation | generation transaction | see O4 |
| Match result → downstream slot | match result recorded or corrected | same transaction | propagate along edges; unrelated matches untouched |

**REQUIREMENT — the missing edge.** Writing stat lines **must** trigger score
derivation and standings recomputation within the same transaction.

**Evidence (FACT):** in the legacy system, saving a box score recomputes nothing.
Game 1971 holds five real stat lines entered by the league owner and still reads
`scheduled 0-0`. That is a missing edge in this graph, and it is the single most
concrete illustration of why this document exists.

---

## Reconstruction requirement

**REQUIREMENT.** Deleting every projection and rebuilding from authoritative rows
alone must produce byte-identical results.

Authoritative rows are exactly: `person`, `player`, `team`, `roster_membership`,
`season`, `division`, `venue`, `game`, `game_result` (where `entered`),
`player_game_stat_line`, `playoff_seed`, `bracket`, `bracket_match`,
`registration`, `sponsor`, `season.config`.

Everything else is reconstructible. If something turns out not to be, it is
secretly authoritative and this document is wrong — fix the document, not the
test.

**Test:** `reconstruction.full-rebuild` — truncate projections, recompute, diff.

---

## Playoff seed: the one genuinely contested fact

Standings are a projection. A seed derives from standings. But a seed, once the
field is announced, is a **historical commitment** — teams were told they were
the 3 seed.

If a game result is corrected in week 9 after seeding, standings legitimately
change. Whether the bracket follows is **not an engineering question**.

**Modelled as:** `playoff_seed` is authoritative once `finalized_at` is set, and
carries `basis_snapshot` — the standings rows it was computed from.

- If policy says **durable**: the seed stands; the snapshot explains it.
- If policy says **reseed**: the seed is recomputed; the snapshot shows what
  changed.
- If policy says **snapshot-based**: already the model.

**POLICY — O4. Default: `durable`.** The seed stands; the snapshot explains any
later divergence, and a correction that would have moved it raises a flagged
discrepancy rather than silently reseeding. All three remain implementable
without schema change, so this is a config edit.

---

## Anti-patterns — rejected by name

| Pattern | Why rejected |
|---|---|
| A second boolean meaning the same as a status enum | S1 evidence — two flags, 16 vs 5 sites |
| Incrementing a counter on an event | Reversal leaves it wrong forever (FACT) |
| Storing a total that is a sum of rows you already have | 3 players already disagree (FACT) |
| A convenience route that writes an authoritative column directly | The weakest of three score routes had zero validation (FACT) |
| Inferring structure from a text label | Bracket progression by round name; required fixes at 24 sites (FACT) |
| A UI control with no mutation behind it | Delete button, no handler, for months (FACT) |
