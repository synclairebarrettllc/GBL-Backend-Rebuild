# 11 — Playoff and Bracket Engine

**Direction: REPLACE.** The legacy playoff system is the single clearest example
of the failure mode this specification exists to prevent, and none of it is kept.

**Evidence (FACT).** Legacy inferred bracket progression from **round name text**.
`playoff_games` was a parallel table with a status column carrying no CHECK
constraint, which wrote `'completed'` while ~45 read sites compared against
`'final'` — every one of those comparisons permanently false, silently. Fixing
progression correctly required changes at 24 sites.

---

## 1. Structure is data, not text

**REQUIREMENT.** Bracket progression is a **foreign key**:
`bracket_match.winner_advances_to_match_id`.

There is no round-name parsing, no "if the round is Semifinal then the next round
is Final", no ordering by label. A match knows exactly one thing about the
future: which match its winner feeds.

**Why this specific design.** Round names are presentation. They get renamed
("Quarterfinal" → "Round of 8"), localised, and typo'd. Structure that depends on
a display string breaks when someone edits a display string — which is precisely
what happened.

`round_number` and `round_label` still exist, **for display only**. No engine
logic may read them.

---

## 2. No parallel table

**REQUIREMENT.** Playoff games are `game` rows. There is no `playoff_games`.

A playoff game is an ordinary game that a `bracket_match` references. It has the
same statuses, the same result engine, the same stat lines, the same CHECK
constraints, and the same scheduler (S23).

**Consequence — this is the fix, stated plainly.** The status drift is
unrepresentable because there is no second status column to drift from. The 45
mismatched comparisons cannot recur because there is one vocabulary
(`04_state-machines.md`).

---

## 3. Seeding

### The operation

```
PlayoffService.finalizeSeeds(season_id) → PlayoffSeed[]
```

**REQUIREMENT — explicit operator action.** Seeds are never computed
automatically when the last game finalises. Someone declares the field.

**Preconditions:** every regular-season game is `finalized`, `cancelled` or
`forfeited`; the seeding tiebreak chain is configured.

### Seeding uses its own tiebreak chain

**S20.** Regular-season and playoff-seeding chains are **separate and separately
ordered**. `09_standings.md` §4 holds the vocabulary; `season.config.tiebreak
.playoff_seeding` holds the chain.

Multi-team ties are **UNKNOWN — O3**, and matter more here than anywhere else: a
3-way tie for the 4 seed determines who hosts and who travels.

### The basis snapshot

**REQUIREMENT.** Each `playoff_seed` row is written with `finalized_at` and
`basis_snapshot` — the standings rows the seed was computed from — in the **same
transaction**.

**Why.** A seed is a historical commitment. Teams were told they were the 3 seed.
Six weeks later, after a correction, "why am I the 4 seed" must be answerable
with what was true at the time. Without the snapshot the question has no answer,
and recomputing current standings answers a different question.

### Durability after a correction — UNKNOWN — O4

If a week-9 result is corrected after seeding, standings legitimately change.
Whether the bracket follows is **not an engineering question**.

| Policy | Behaviour |
|---|---|
| **Durable** | Seeds stand; the snapshot explains the discrepancy |
| **Reseed** | Seeds recomputed; the snapshot shows exactly what changed |
| **Snapshot-based** | Already the model — seeds were always the snapshot |

**All three are implementable against this schema with no change.** The
specification does not choose. **Interim:** seeds are durable and a correction
that would alter them raises a flagged discrepancy for the operator rather than
silently reseeding or silently ignoring.

---

## 4. Bracket generation

```
BracketService.generateBracket(season_id, format) → Bracket
```

**REQUIREMENT (S21).** Formats are parameters. Nothing about "8 teams,
single-elimination, three rounds" is hardcoded.

```
format = {
  type:            'single_elimination' | 'double_elimination' | 'group_then_bracket',
  team_count:      <int>,
  seeding_pattern: '1v8' | '1v8_reseed' | 'custom',
  byes:            <int>,
  series_length:   <int>,          // 1 = single game
  home_court_rule: <config>
}
```

**REQUIREMENT — complete structure before seeding.** `generateBracket` creates
**every** match and **every** `winner_advances_to_match_id` edge before the
bracket may leave `draft`. A partially built bracket is not seedable
(`04_state-machines.md`).

This is the structural guarantee that makes progression-by-label impossible: the
path from the first round to the final exists as data before a single game is
played.

**Byes** are modelled as a match with one participant resolved and the other
`NULL` by construction, which resolves immediately. A bye is not a special case
in the progression logic — it is an ordinary match that is already decided.

---

## 5. Match lifecycle and propagation

States and transitions are in `04_state-machines.md`. The engine behaviour:

### Slot resolution

A match is `pending` while either participant is unresolved. When an upstream
match completes, its winner fills the downstream slot **along the edge**. When
both slots are filled, the match becomes `ready` and its games may be scheduled.

**REQUIREMENT.** Propagation is **one hop per transaction**, following the FK. No
service scans for "the next round", sorts by round number, or matches on a label.

### Series

`series_length` determines when a match is decided. A best-of-3 match references
up to three games; the match completes when one team reaches the required wins.

**REQUIREMENT.** Match completion is derived from its games' results, not entered
directly. Same rule as scores in `08_game-results.md` — one authority per fact.

### Correction propagation — bounded

When a finalised playoff game is corrected (`08_game-results.md` §7):

1. The containing `bracket_match` is re-evaluated.
2. If the winner **did not change**, nothing propagates. Full stop.
3. If it changed, the downstream slot is refilled along the edge, and the rule
   repeats **only where a winner actually changed**.

**REQUIREMENT — bounded blast radius.** Every match not reachable along
progression edges from the corrected game is **byte-identical** afterward.
Tested as `bracket.correction-bounded`.

**Why this is a named requirement.** A recompute-everything approach appears
correct and is catastrophic in practice: correcting one first-round score would
rewrite the entire bracket including matches already played, and nobody would be
able to tell which changes were intentional.

---

## 6. Home court, venues, timing

Playoff games are scheduled by the scheduler under the same constraints as every
other game (S22, S23). A bracket match stores **no date and no venue** — its
games do.

`home_court_rule` in the format config determines which seed is home. The rule is
configuration; the assignment is a scheduling fact on the game.

---

## 7. What the playoff engine never does

| Never | Because |
|---|---|
| Reads a round name to decide anything | The exact legacy defect |
| Writes to a separate playoff games table | One vocabulary, one status, one CHECK |
| Computes seeds automatically at season end | Declaring the field is an operator act |
| Writes a seed without its basis snapshot | The seed becomes unexplainable |
| Sets a match winner directly | Derived from its games |
| Recomputes the whole bracket on a correction | Unbounded blast radius |
| Stores a date on a match | S23 — the scheduler owns timing |

---

## 8. Acceptance tests

| Test | Asserts |
|---|---|
| `bracket.no-parallel-table` | Schema check: playoff games are `game` rows |
| `bracket.structural-progression` | Renaming every round label changes no progression |
| `bracket.structure-complete-before-seed` | A bracket with a missing edge cannot leave `draft` |
| `bracket.propagation` | A completed match fills exactly its downstream slot |
| `bracket.bye-resolves` | A bye match resolves without special-case logic |
| `bracket.series-derived` | A best-of-N match completes from game results only |
| `bracket.correction-bounded` | Unrelated matches byte-identical after a correction |
| `bracket.correction-no-change-no-propagate` | A correction that preserves the winner propagates nothing |
| `seed.basis-snapshot-written` | Every finalized seed has its standings basis, same transaction |
| `seed.durable-flags-discrepancy` | A post-seeding correction raises a flag, not a silent reseed |
| `seed.separate-chain` | Playoff seeding uses the playoff chain, not the regular-season chain |
| `bracket.no-date-on-match` | Schema check: matches carry no timing columns |

**`bracket.structural-progression` is the definitive regression test.** Rename
every round in the database; if any bracket behaviour changes, the legacy defect
has returned.
