# 07 — Statistics Engine and Live Tracker

**Direction: PRESERVE the stat-line grain; BUILD FRESH the derivation chain,
scoring representation, and the live entry path.**

The grain — one line per Player per Game — is the strongest concept in the legacy
system. It absorbed soft delete, provenance and external identity without
distortion. Everything above it is rebuilt.

---

## 1. Authoritative model

`player_game_stat_line` is authoritative for what a player did in a game. See
`05_database.md` for the schema.

**Stored (inputs):** `two_pointers_made`, `three_pointers_made`,
`free_throws_made`, optional attempts, `offensive_rebounds`,
`defensive_rebounds`, `assists`, `steals`, `blocks`, `turnovers`,
`personal_fouls`, `plus_minus`.

**Derived — never stored as independent columns:**

```
points           = 2·two_pointers_made + 3·three_pointers_made + free_throws_made
field_goals_made = two_pointers_made + three_pointers_made
field_goals_attempted = two_pointers_attempted + three_pointers_attempted   (NULL if either is NULL)
total_rebounds   = offensive_rebounds + defensive_rebounds
```

### Why scoring is stored as 2PM/3PM

**Evidence (FACT).** Legacy collected FGM, which silently includes three-pointers.
A scorekeeper recording "3 twos and 2 threes" entered FGM=3, 3PM=2 — producing
**8 points instead of 12**. The relationship "more threes than field goals" was
also rejected outright, so a legitimate line could not be saved.

Splitting the inputs makes the error **unrepresentable** rather than validated
against. There is no combined-makes field to misread. This is **rule G1** in
`01_principles.md` (not Gate G1), and it is the clearest case for it.

### Why attempts are nullable

**Evidence (FACT).** Legacy validation required FGA and rejected `fgm > fga`.
GBL records makes, not attempts, so FGA arrived as `0`, which the validator read
as "zero attempts" rather than "not tracked" — and **every real stat line was
rejected**. This is why `player_game_stats` was empty for the life of the app.

**REQUIREMENT.** `NULL` attempts mean *not tracked*. `0` means *zero attempts*.
They are different values with different meanings and must never be conflated. A
percentage over a `NULL` denominator is `NULL`, not `0`.

---

## 2. Validation

Applied by StatsService on every write, in the transaction.

### Hard rules — always enforced

| Rule | Reason |
|---|---|
| All counting stats ≥ 0 | database `CHECK` |
| `made ≤ attempted` when attempted is present | database `CHECK` |
| Player has a roster membership on the game's team, **or** the write declares a fill-in | fill-ins are real (FACT) |
| One line per `(game_id, player_id)` | database `UNIQUE` |
| Game is not `finalized` unless this is a correction | state machine |

### Rules that are NOT enforced

**REQUIREMENT.** Do **not** enforce a relationship between a player's stat line
and the team score. Do **not** require every rostered player to have a line. Do
**not** reject a line for being statistically improbable.

**Evidence (FACT):** 13 legacy games have box scores that do not sum to their own
posted score. That is source-side reality, faithfully reproduced. A validator
that rejects it would make real games unrecordable.

**POLICY — O5. Default: `on_mismatch: 'warn'`.** A box score that does not sum to
the team score does **not** block finalisation. The discrepancy is detected
automatically and recorded with both values, and an authorized person finalises
with a stated reason. The hook is specified in `08_game-results.md` §4.

---

## 3. Aggregation

### Player season totals — projection, never stored

```
totals(player, season) = Σ stat lines
                         WHERE player_id = ?
                           AND game.season_id = ?
                           AND game.status IN ('completed','finalized')
                           AND game.deleted_at IS NULL
```

**REQUIREMENT.** No column stores a player's season totals.

**Evidence (FACT):** `players.season_*` (8 columns) plus `games_played` were
written on every stat save and read by nothing — and **3 players already
disagreed with their own stat lines**. A maintained, unread, drifting cache is
the worst of every option.

**Games played** counts stat lines, not roster appearances. A player with a line
recording all zeros played; a player with no line did not.

### Team box score — projection

Team totals for a game are the sum of that game's lines grouped by `team_id` on
the line — not by roster lookup. This is what makes fill-ins correct: the two
Clippers players who appeared for the Kings (FACT) contribute to the Kings' box
score, because their lines say so.

### Leaderboards

Ranked projections over season totals. Season-scoped, always.

**REQUIREMENT.** Leaderboards exclude players with zero games played.

**Evidence (FACT):** the legacy `/players` endpoint had no such filter and ranked
**264 players including 31 with zero games**, one of them literally named
"Kobe (DNP)".

**Minimum-games qualification** for rate statistics comes from season config
(`13_configuration.md`), which already carries a `min_games_for_leaderboard`
concept from the legacy settings table.

---

## 4. Composite metrics

**Product requirement (S8, S9).** NBA-caliber depth: shooting percentages,
plus-minus, and efficiency ratings. Season awards **structurally depend** on
these, and the stated purpose is that players can compute and verify them
themselves.

### Derivable now

```
FG%   = field_goals_made / field_goals_attempted            (NULL if attempts NULL)
3P%   = three_pointers_made / three_pointers_attempted      (NULL if attempts NULL)
FT%   = free_throws_made / free_throws_attempted            (NULL if attempts NULL)
eFG%  = (field_goals_made + 0.5·three_pointers_made) / field_goals_attempted
PPG, RPG, APG, SPG, BPG = total / games_played
```

### O1 — the composite formulas — DEFAULT set

PER, PIR and "efficiency rating" each have **multiple published definitions that
produce different results**, so the formula in use must be **published**, not
assumed. S9's stated purpose is that a player can redo the arithmetic themselves
and accept the outcome; a formula nobody can reproduce defeats the reason the
metric exists.

**Default: the standard PIR/EFF formula**, chosen because it is computable from
statistics GBL already collects and is arithmetically transparent.

**Slot:**

```
season.config.composite_metrics = [
  { key: <string>, display_name: <string>, formula: <POLICY — O1>, decimals: <int> }
]
```

**RECOMMENDATION (not binding):** adopt the standard PIR/EFF formula, since it is
computable from stats GBL already collects and is arithmetically transparent:

```
PIR = (points + rebounds + assists + steals + blocks)
    − (missed field goals + missed free throws + turnovers)
```

Note this needs **attempts** to compute misses. With attempts untracked, PIR is
`NULL`. That is an honest outcome and should be surfaced rather than approximated
— an award computed from a silently substituted formula is worse than no award.

---

## 5. The live stat tracker

**Core product requirement (S3).** Not an administrative import.

### Access model

**REQUIREMENT (S4).** The tracker is **anonymous**. No scorekeeper accounts, no
individual logins. Anyone at the scorer's table operates it.

**REQUIREMENT.** Access is by **per-game capability token**, not a login:

- The admin generates a tracker link for a specific game.
- The token authorises writes **to that game's stat lines only**.
- It expires when the game is finalised, or after a configured window.
- It grants no other capability — it cannot read other games, edit rosters, or
  reach any admin surface.

This is how an anonymous tool gets a bounded write surface. **The token is the
authorization, and the game is the scope.**

### Permitted mutation surface

The tracker may:

- create and update stat lines **for its game**
- transition its game `scheduled → in_progress`
- submit, transitioning `in_progress → completed`

The tracker may **not**: finalize, correct a finalized game, alter rosters,
change the schedule, or touch any other game.

### Progressive persistence

**REQUIREMENT (S6).** Stats are persisted **during** entry, not on submit. If the
tab closes or the app is interrupted mid-game, entered data survives.

**Implementation:** every stat increment is a write. There is no client-side
buffer holding a game's worth of unsaved work.

**Consequence — this is why idempotency matters here specifically.** A tracker on
a flaky connection will retry. Each write therefore carries a client-generated
`operation_id`; a repeat of the same `operation_id` is a no-op returning the
current state.

**Evidence for the shape (FACT):** the legacy stat sheet held everything in
client state and saved once. A re-render lost it, and a partial save silently
overwrote a valid line with garbage.

### Real-time propagation

**REQUIREMENT.** Stat writes push to public read views without a page refresh
(S3: "pushes real-time updates to the website").

**RECOMMENDATION (O7-adjacent).** Durable Objects + WebSockets on the working
default platform. Cloudflare's own documentation names live sports scores as the
canonical use case for this pattern. Not binding; the requirement is real-time
propagation, not a specific mechanism.

### Offline

**DEFERRED (S7, via Gate G1's closure).** The tracker assumes live connectivity. Offline
capture with later sync is explicitly **not** solved in this build.

**REQUIREMENT.** The design must not *preclude* it. Because every write is an
idempotent operation with a client-generated id, a future offline queue replays
naturally. That is the only accommodation made — no offline machinery is built.

### Correction

Corrections during the game are ordinary updates. Corrections after finalisation
go through the admin path (`08_game-results.md`), not the tracker — the token has
expired by then.

---

## 6. Derivation into the game result

**REQUIREMENT — this is the edge the legacy system was missing.**

When a stat line is written and the game's result is `derived`:

1. Recompute team scores from the game's lines, in the same transaction.
2. Update `game_result.home_score` / `away_score`.
3. If the game is `finalized`, recompute standings for the season.
4. If the game belongs to a bracket match, re-evaluate that match.

**Evidence (FACT).** Legacy saved stat lines and recomputed nothing. Game 1971
holds five real stat lines entered by the league owner and still reads
`scheduled 0-0`. That single row is the clearest statement of why this
specification exists.

**Transaction boundary:** stat write and score derivation are **one transaction**.
Standings recomputation may be in the same transaction or a committed follow-up,
provided a failure leaves standings recomputable — never silently stale.

---

## 7. Acceptance tests

| Test | Asserts |
|---|---|
| `stats.scoring-arithmetic` | 3 twos + 2 threes = **12**, not 8. The legacy bug, as a permanent test |
| `stats.attempts-null-vs-zero` | `NULL` attempts yields `NULL` percentage; `0` attempts yields `0` |
| `stats.makes-only-line-accepted` | A line with makes and no attempts saves successfully |
| `stats.no-stored-totals` | No column anywhere stores player season totals |
| `stats.totals-recompute-equality` | Recomputed totals equal projected totals for every player |
| `stats.fill-in-attribution` | A line whose `team_id` differs from the player's roster counts to the line's team |
| `stats.derivation-edge` | Writing a stat line updates the derived score in the same transaction |
| `stats.leaderboard-excludes-zero-games` | Zero-game players do not appear |
| `tracker.token-scope` | A tracker token cannot write to another game |
| `tracker.token-expiry` | A token is rejected after finalisation |
| `tracker.progressive-save` | Data survives simulated mid-game interruption |
| `tracker.idempotent-retry` | Replaying an `operation_id` changes nothing |
| `tracker.cannot-finalize` | The tracker cannot finalize or correct a finalized game |

**Every one of these except the token tests encodes a verified historical
failure.** They are regression tests for bugs that actually happened, not
hypothetical coverage.
