# 08 — Game Result Engine

**Direction: BUILD FRESH.** There is no legacy component to preserve. Scores were
written by three different routes with three different rule sets, and the one
edge that mattered — stat lines producing a score — did not exist.

---

## 1. The single authority

`game_result` is the only place a score lives. `GameResultService` is the only
code that writes it.

**REQUIREMENT.** `game` carries **no** score columns. Not as a cache, not for
convenience, not for the public API's benefit.

**Evidence (FACT).** Legacy stored `home_score`/`away_score` on `games`, written
by three routes:

| Route | Validation |
|---|---|
| admin score update | 4 checks |
| game finalization | 4 checks |
| a convenience endpoint | **0 checks** |

The rules that applied to a score depended on which URL was used. Removing the
column is what makes that class of defect unrepresentable.

---

## 2. Provenance: `result_source` — ADR-010

**Decision status: ACCEPTED** (ADR-010, Score Authority). The direction is
ratified; the discrepancy policy remains open as O5 (§4).

```
result_source ∈ { 'derived', 'entered' }
```

| Value | Meaning | Who may write the score |
|---|---|---|
| `derived` | computed from `player_game_stat_line` | StatsService cascade **only** |
| `entered` | typed by an operator; no stat lines exist | GameResultService.enterResult |

### The authority rule, stated by state — not by slogan

**REQUIREMENT.** When a result is designated `derived`, the score is a
**projection computed from authoritative stat lines**, and direct score
overwrite is **refused**.

**REQUIREMENT.** `player_game_stat_line` is authoritative for player-level
statistics. `GameResultService` remains the single canonical mutation authority
for official game-result state. `result_source` is **explicit provenance, not a
second authority**.

**REQUIREMENT.** Direct score entry is permitted only where the state model
allows it — that is, `entered`, which requires that no stat lines exist. A caller
cannot manufacture a competing authoritative score by typing over a
stat-derived result: `enterResult` on a game with stat lines is rejected with
`RESULT_WOULD_CONTRADICT_STATS`.

> **Why this is worded by state and not as "stats beat direct entry."** A
> universal slogan would silently pre-decide cases the model has not yet
> defined: games with no box score, forfeits, legacy imports, incomplete stat
> capture, and correction workflows. Authority is established by the explicit
> `result_source` state, so each of those cases is decided by its own designated
> source rather than by a general precedence rule.

### Import precedence — a separate rule

**REQUIREMENT.** An import, backfill, or any bulk process must not overwrite a
result that was authored locally, whether `derived` or `entered`. It may create
a result where none exists. It may never overwrite one.

This is a distinct rule from the authority rule above, and is named separately
because the two are often conflated: the first governs *which store owns a
score*, the second governs *who may act on it*.

**Evidence (FACT) — verified in this repository on 2026-09-09:**

- Migration `0029_games_soft_delete_and_score_source.sql` adds
  `games.score_source TEXT DEFAULT NULL CHECK (score_source IN ('live','imported'))`.
- The importer guard at `scripts/import-recleague.cjs:409-420` skips any game
  where `score_source = 'live'`, counts it as `protectedLive`, and logs **both
  values** when they disagree (`ours X-Y, source says A-B`).
- The write paths in `src/index.tsx` default to `'live'` (lines 3082, 3692,
  3879), and the import path sets `'imported'` only where the column is `NULL`
  or already `'imported'` (line 3882) — so a caller that forgets to declare
  itself **fails safe**.

**Correction to an earlier draft of this document.** A previous version cited "a
deliberately absurd 99-point stat line" surviving an import. That figure is not
reproducible from the current database and is withdrawn — it came from a sandbox
run that was not preserved. The verifiable evidence is the code and schema above,
plus game 1971 (§3). The withdrawn number changes nothing about the rule; a
figure that cannot be reproduced does not belong in a specification.

### Transitioning between sources

Entering the first stat line on an `entered` game converts it to `derived` — and
**the operator is told the entered score is being replaced by the box score**.
This is the only legal direction. There is no path from `derived` back to
`entered` that does not go through deleting every stat line.

---

## 3. Derivation

```
home_score = Σ points(line) for lines where line.team_id = game.home_team_id
away_score = Σ points(line) for lines where line.team_id = game.away_team_id
points(line) = 2·2PM + 3·3PM + FTM
```

Attribution is by **the stat line's own `team_id`**, never by roster lookup.

**Evidence (FACT).** Two Clippers players appeared for the Kings. Deriving
attribution from the roster would credit their points to the wrong team, and
correcting the roster afterward would silently change a completed game's score.

**REQUIREMENT.** Derivation runs in the same transaction as the stat write. There
is no queue, no nightly job, and no "recompute" button that a human has to
remember to press.

**Evidence (FACT) — verified in this repository on 2026-09-09.** Game 1971 is the
single row that demonstrates both halves of ADR-010 at once:

| Property | Value |
|---|---|
| `score_source` | `live` — the only such game in the database |
| Stat lines | 5, totalling **45** (team 11) and **36** (team 14) |
| `home_score` / `away_score` | **0 / 0** |
| `status` | `scheduled` |

The guard works — the importer leaves this game alone. The derivation edge does
not exist — 81 points of real, live-entered box score sit next to a `scheduled
0-0` result. One row, both the control that succeeded and the edge that was
never built.

---

## 4. Stat-to-score discrepancy — UNKNOWN — O5 / POLICY-013

**The question is no longer "should scores derive from stats?"** — ADR-010
settles that (§2). What remains open is narrower and genuinely a league decision:

> **When authoritative stat lines mathematically disagree with an independently
> recorded or posted game score, what happens?**

**Why it cannot be defaulted.** 13 legacy games have box scores that do not sum
to their posted score (FACT). If the rule is "must sum", those games are
unfinalisable and the league's own history is rejected by its own system. If the
rule is "need not sum", a scorekeeper who missed a basket produces a standings
row nobody can reconstruct.

### Settled regardless of how O5 lands

These four hold under every candidate policy, so they are **REQUIREMENTS now**,
not part of the open question:

1. **Detection is automatic.** The service computes the stat-derived score and
   compares it to any independently recorded score on every write.
2. **Both values are recorded**, with the discrepancy, on the result row.
3. **A game never silently holds two competing official scores.** One is the
   official result per `result_source`; the other is retained as a recorded
   observation, explicitly labelled as such.
4. **Any override carries provenance and a correction path** — it is reachable
   only through `correctFinalizedGame`, never by direct write.

**Precedent (FACT).** The legacy importer already implements 1–2: on a protected
game it logs `ours X-Y, source says A-B` rather than reconciling
(`scripts/import-recleague.cjs:409-420`). The comment above it records the
deliberate choice: *score from the header, lines from the tables, no
reconciling.* The new system formalises that instead of inventing it.

### The open part — finalisation behaviour

**Typed slot:**

```
season.config.finalization_rule = {
  require_box_score_sum: <UNKNOWN — O5: boolean>,
  tolerance_points:      <UNKNOWN — O5: integer | null>,
  on_mismatch:           <UNKNOWN — O5: 'block' | 'warn' | 'allow'>,
  override_requires:     <UNKNOWN — O5: 'none' | 'reason' | 'named_authority'>
}
```

| Candidate | Consequence |
|---|---|
| `block` | Discrepant games cannot finalise; the 13 legacy games would be unfinalisable on migration |
| `warn` | Authorized finalisation proceeds; the discrepancy is visible and recorded |
| `allow` | Recorded silently; standings move without anyone being told |

**Interim behaviour until decided:** detection, recording and both-value
retention are **active** (they are requirements above). Finalisation does **not**
block. The decision can therefore be applied retroactively to already-recorded
discrepancies without re-deriving anything.

---

## 5. Forfeits — UNKNOWN — O2

A forfeit is a real league outcome and the schema supports it. What it *counts
as* is policy.

**Typed slot:**

```
season.config.forfeit_rule = {
  counts_as:        <UNKNOWN — O2: 'win_loss' | 'no_contest'>,
  awarded_score:    <UNKNOWN — O2: [int, int] | null>,
  player_stats:     <UNKNOWN — O2: 'none' | 'preserved'>,
  affects_tiebreak: <UNKNOWN — O2: boolean>
}
```

**REQUIREMENT regardless of the decision.** A forfeited game keeps its
`forfeited` status permanently. It is never rewritten as a normal win, because
the distinction is exactly what a player will ask about.

---

## 6. Finalisation and locking

`finalized` means: this outcome is settled, standings may depend on it, and
changing it requires a named correction.

**REQUIREMENT.** Finalisation is **explicit and operator-driven**. A game does not
finalise because time passed, because the tracker submitted, or because a
scheduled job ran.

**What finalisation opens:** standings become authoritative for seeding; the
result becomes eligible to resolve a bracket match; the tracker token for that
game expires.

**What it locks:** stat lines, scores, and participants — all reachable only
through `correctFinalizedGame`.

---

## 7. Correction

Corrections are expected. A scorekeeper miscounts; a protest is upheld; a fill-in
was recorded on the wrong team. The system's job is to make correction **safe and
traceable**, not to make it hard.

### The correction cascade — enumerated

1. Game → `completed`; result → `provisional`
2. Stat lines become editable
3. On re-finalisation:
   - standings for the season recomputed
   - any `bracket_match` containing this game re-evaluated
   - if the match winner changes, propagate **one hop along
     `winner_advances_to_match_id`**, repeating only where a winner actually
     changed
4. Playoff seeds: **UNKNOWN — O4**

**REQUIREMENT — bounded.** Every match not reachable from the corrected game
along progression edges is byte-identical afterward. Tested as
`bracket.correction-bounded`.

### The correction record

**Settled behaviour (S25).** Corrections are **simple overwrites**. No change-log
UI, no approval workflow, no user-facing history. The specification follows this.

**RECOMMENDATION — not binding, Board decision open.** Retain one internal row per
correction of a *finalised* result: timestamp, previous scores, new scores,
operator-stated reason. This is narrower than an audit trail — it logs
corrections of settled outcomes, not ordinary activity — and it exists because
"why did our win become a loss" is a question the league will actually be asked.

If declined, correction still works exactly as specified; only the explanation is
unavailable afterward. Nothing else in this document depends on it. See the
S25-versus-anonymous-tracker tension in `20_decisions.md`.

---

## 8. What the result engine never does

| Never | Because |
|---|---|
| Writes a score column on `game` | No such column exists |
| Lets a route set a score directly | R5, and three routes is how this started |
| Edits a `derived` score | Two homes for one fact |
| Overwrites a locally authored result during import | Import precedence (§2) |
| Lets a caller type over a `derived` score | ADR-010 — authority is set by state |
| Infers finalisation from elapsed time | Explicit transitions only |
| Deletes stat lines to "clean up" a result | Stat lines are authoritative |

---

## 9. Acceptance tests

| Test | Asserts |
|---|---|
| `result.no-score-on-game` | Schema check: `game` has no score column |
| `result.single-authority` | Only GameResultService writes `game_result` scores |
| `result.derived-from-lines` | Score equals the sum of line points, by line `team_id` |
| `result.fill-in-attribution` | A fill-in's points go to the team on the line |
| `result.derived-not-editable` | No path edits a derived score directly |
| `result.entered-refused-with-stats` | `enterResult` is rejected when lines exist |
| `result.import-precedence` | An import leaves a locally authored result untouched |
| `result.source-transition` | First stat line converts `entered` → `derived` and warns |
| `result.finalize-explicit` | No time-based or automatic finalisation exists |
| `result.correction-cascade` | Correction recomputes standings and the affected match |
| `result.correction-bounded` | Unrelated matches are byte-identical after a correction |
| `result.forfeit-persists` | A forfeited game never becomes a normal result |

### ADR-010 conformance suite

Named separately because these five together constitute the acceptance evidence
for the ratified score-authority decision.

| Test | Asserts |
|---|---|
| `adr010.stat-lines-produce-score` | Given stat lines, the derived score equals the expected sum, by line `team_id` |
| `adr010.derived-overwrite-refused` | A direct score write against a `derived` result is **refused**, not merged, not silently ignored |
| `adr010.replay-does-not-alter-result` | Replaying a stat write with the same `operation_id` leaves the result byte-identical |
| `adr010.correction-propagates-deterministically` | Correcting a stat line recomputes the score, standings and any bracket match — identically on every run |
| `adr010.discrepancy-behaviour` | A stat-to-score disagreement is **detected, recorded with both values**, and finalisation follows `finalization_rule` (O5) |

**`adr010.discrepancy-behaviour` is partially parameterised on an open
decision.** Its detection-and-recording assertions are active now; its
finalisation assertion reads `finalization_rule` and is a no-op until O5 lands.
The test exists and runs from day one so the policy drops in without new test
scaffolding.
