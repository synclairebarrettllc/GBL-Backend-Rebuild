# 09 — Standings Engine

**Direction: BUILD FRESH.** The legacy standings read `teams.wins`/`teams.losses`
— accumulator columns that were both incremented on events and treated as truth.
Two drift paths were confirmed live. Nothing here is preserved.

---

## 1. Standings are a projection. Full stop.

**REQUIREMENT.** No table stores a team's record, win percentage, rank, streak,
or point differential.

```
StandingsService.compute(season_id, scope) → StandingsTable
```

Pure function. Same inputs, same output, every time. `StandingsService` has **no
mutation methods** (`06_mutations.md` §3) — if one is ever added, the architecture
has been violated.

**Evidence (FACT).** Legacy incremented `teams.wins` when a game was finalised.
Reversing a game did not reliably decrement it, so a single correction left the
column wrong permanently, with nothing to detect it. An accumulator that cannot
survive a reversal is not a record; it is a rumour.

### If it is cached

Caching is permitted under the four rules in `03_source-of-truth.md`: one writer
(the derivation function), never read as authority by a mutation, tested against
a fresh recompute, and fully rebuildable. Default is **not cached** — GBL's scale
does not require it.

---

## 2. What goes into a record

### Games counted

```
countable(game) = game.deleted_at IS NULL
              AND game.status IN ('finalized', <forfeited per O2>)
              AND game.season_id = ?
```

**REQUIREMENT.** Only `finalized` games count. A `completed` game has a result
but has not been declared settled; including it would let standings move before
anyone approved the outcome.

**Explicitly excluded:** deleted, cancelled, scheduled, in-progress, and games
belonging to another season. Playoff games do **not** count toward regular-season
standings.

### Record fields — all derived

| Field | Definition |
|---|---|
| `wins` | countable games where the team's score is higher |
| `losses` | countable games where the team's score is lower |
| `ties` | countable games with equal scores (**see below**) |
| `games_played` | `wins + losses + ties` |
| `win_pct` | `(wins + 0.5·ties) / games_played`, `NULL` when `games_played = 0` |
| `points_for` | Σ the team's scores |
| `points_against` | Σ opponents' scores |
| `point_differential` | `points_for − points_against` |
| `home_record`, `away_record` | same, partitioned |
| `division_record` | countable games against teams in the same division |
| `streak` | derived from the ordered game sequence |
| `last_10` | derived from the ordered game sequence |

**Ties.** Basketball does not normally tie, but the schema permits equal scores
and 13 legacy games already fail to sum to their own posted scores (FACT). The
engine computes `ties` rather than crashing or silently classifying a tie as a
loss. Whether GBL's rules permit a tie at all is a **league** question; the
engine's behaviour if one occurs is specified here regardless.

**`win_pct` with zero games is `NULL`, not `0`.** A team that has not played is
not a team that has lost. Same discipline as `NULL` attempts in
`07_statistics.md`.

---

## 3. Scope

**S13.** GBL is marketed as one league with two conferences and modelled
internally as **two divisions**. The engine takes scope as a parameter:

```
scope ∈ { league, division(division_id), custom(team_ids) }
```

The marketing vocabulary lives in presentation. The engine knows only divisions.
This is why a rename from "conference" to anything else is a copy change, not a
migration.

---

## 4. Tiebreaking

### Settled (S20)

- Tiebreak chains are **admin-configurable and reorderable**.
- **Regular season and playoff seeding use separate chains.**
- **Default first criterion: point differential.**

### Configuration shape

```
season.config.tiebreak = {
  regular_season: [ <criterion>, ... ],
  playoff_seeding: [ <criterion>, ... ],
  multi_team_rule: <UNKNOWN — O3>,
  final_fallback:  <criterion>          // must be total-ordering
}
```

### Criterion vocabulary

Each is a pure function over the countable game set. The engine ships the full
vocabulary; the chain selects and orders it.

| Criterion | Definition |
|---|---|
| `point_differential` | `points_for − points_against` (S20 default) |
| `head_to_head` | record among the tied teams only |
| `division_record` | record within the division |
| `points_for` | total scored |
| `points_against` | total allowed, ascending |
| `wins` | total wins, ignoring games played |
| `coin_flip` | seeded by season id + team ids — **deterministic**, reproducible, and auditable |

**REQUIREMENT — the chain must terminate in a total ordering.** If every
criterion ties, the engine must still return a stable order and must **say** that
the tie reached the fallback. Two teams in an arbitrary, unexplained order is how
a league loses an argument it should have won.

**`coin_flip` is deterministic by design.** A random tiebreak that returns a
different answer on refresh is unusable. Seeding it from stable identifiers means
the result can be recomputed and defended.

### Multi-team ties — UNKNOWN — O3

When three or more teams tie, the following are all defensible and produce
**different brackets**:

1. Apply the chain to the whole tied group at once.
2. Build a sub-table among the tied teams, then apply the chain within it.
3. Break the top team out, then **restart the chain** for the remainder.
4. Skip `head_to_head` entirely when the tied teams have not all played
   each other.

**The specification does not choose.** The engine implements the selected rule as
a strategy; all four are implementable without schema change.

**REQUIREMENT for the interim.** Until O3 is decided, a multi-team tie is
computed with option 1 **and flagged in the output** as unresolved-by-policy, so
it is visible rather than silently decided.

---

## 5. Forfeits — UNKNOWN — O2

`countable()` above carries a typed slot for whether `forfeited` games enter the
record, and `08_game-results.md` §5 holds the full configuration shape. The
standings engine reads that config; it does not decide.

---

## 6. Determinism and explainability

**REQUIREMENT.** The output of `compute()` is a function of: countable games,
their results, and the season config version. Nothing else — not wall-clock time,
not row insertion order, not a database-default sort.

**REQUIREMENT.** Every standings table carries the **config version** it was
computed under. This is what makes O12 (retroactivity) decidable later without
rework: the stamp exists either way.

**REQUIREMENT — explain the ordering.** For any two adjacent teams, the engine can
state which criterion separated them.

**Why this is a requirement and not a nicety.** S9's stated goal is that players
can verify the numbers themselves. A standings table nobody can interrogate
produces exactly the argument the league is trying to avoid, and the engineering
cost is recording which criterion fired.

---

## 7. Recomputation triggers

Standings are recomputed — never incremented — when:

- a game is finalised or unfinalised
- a finalised game's result changes (correction cascade, `08_game-results.md`)
- a game is cancelled or deleted
- season config changes (subject to O12)

**REQUIREMENT.** There is no code path that adjusts a standings value in place.
Recompute-from-source is the only update mechanism.

---

## 8. Acceptance tests

| Test | Asserts |
|---|---|
| `standings.no-stored-record` | Schema check: no wins/losses/rank/differential column exists |
| `standings.no-mutations` | StandingsService exposes no write method |
| `standings.recompute-equality` | Recomputed table equals prior table when nothing changed |
| `standings.deterministic` | Identical output across 100 runs and across insertion orders |
| `standings.correction-reverses` | Reversing a finalised game restores the exact prior table |
| `standings.excludes-non-final` | Completed-but-not-finalized games do not move standings |
| `standings.excludes-deleted` | Soft-deleted games are absent from every field |
| `standings.playoffs-excluded` | Bracket games do not affect regular-season standings |
| `standings.zero-games-null-pct` | A team with no games has `NULL` win pct, not `0.000` |
| `standings.tiebreak-order-applied` | Reordering the chain reorders the table accordingly |
| `standings.tiebreak-total-order` | Every tie resolves to a stable order; fallback is reported |
| `standings.coin-flip-stable` | The seeded tiebreak returns the same result every run |
| `standings.multi-team-flagged` | A 3-way tie is flagged as unresolved-by-policy while O3 is open |
| `standings.config-version-stamped` | Every computed table names its config version |
| `standings.explains-adjacent` | The engine names the separating criterion for any adjacent pair |

**`standings.correction-reverses` is the regression test for the legacy defect.**
An accumulator passes the forward test and fails this one.
