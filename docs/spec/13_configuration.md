# 13 — Configuration

**Direction: BUILD FRESH.** Legacy had a `settings` table read in a handful of
places while most behaviour was hardcoded. S21 requires the opposite: the engines
are parameter-driven and the league's rules live in data.

---

## 1. What is configuration, and what is not

| Kind | Home | Changed by |
|---|---|---|
| **League rules** — tiebreaks, forfeits, eligibility, formats | `season.config` | admin |
| **Structural invariants** — one active season, one line per player per game | database constraints | migration only |
| **Facts** — games, players, scores | tables | domain services |
| **Deployment settings** — bindings, secrets, environment | platform config | operations |

**REQUIREMENT.** A league rule is never a code constant. If a board member could
plausibly want it different next season, it is configuration.

**REQUIREMENT — the converse.** A structural invariant is never configuration.
"Can two seasons be active at once" is not a setting; it is a partial unique
index. Making an invariant configurable is how it gets turned off during an
incident and left off.

---

## 2. Configuration is season-scoped

**REQUIREMENT.** `season.config` is the unit. Rules change between seasons, and a
season's completed games must remain explicable under the rules they were played
under.

League-level defaults may exist as a template that seeds a new season's config.
Once the season exists, its config is its own — editing the template does not
reach back into a running season.

---

## 3. Validation

**REQUIREMENT.** `season.config` is validated against a schema on every write
(`ConfigService.updateSeasonConfig`). An invalid config is rejected at the
mutation boundary.

**REQUIREMENT.** A season cannot be activated with an invalid config
(`06_mutations.md` §4.3). This is the gate that prevents a season from starting
with, say, an empty tiebreak chain that only fails in week 6 when two teams tie.

**REQUIREMENT.** Every engine reading config validates that the keys it needs are
present and **fails loudly** if they are not. A missing tiebreak chain must not
degrade to an implicit default.

**Evidence (FACT).** The legacy pattern of silent defaults is exactly how
`playoff_games.status` drifted — nothing said no, so nothing was noticed.

---

## 4. Versioning

**REQUIREMENT.** Every config write produces a new version. Every standings
computation, seed snapshot and bracket generation stamps the config version it
used.

This is what keeps **O12** (retroactivity) a decidable question rather than a
rework: whether completed weeks re-rank under a changed chain is policy, but
either answer needs to know which config produced which output. The stamp costs
nothing and is unrecoverable after the fact.

---

## 5. The configuration schema

This is the complete surface. **Every `POLICY` slot below has a value in
`20_decisions.md` Part 2** — build that value. A builder must not substitute its
own, and must not let code supply one silently: a missing key still fails loudly
(§6).

```
season.config = {

  // ── Standings and tiebreaks ─────────────────────────  09_standings.md
  tiebreak: {
    regular_season:  [ <criterion>, ... ],      // S20 — default: point_differential
    playoff_seeding: [ <criterion>, ... ],      // S20 — separate chain
    multi_team_rule: <POLICY — O3>,
    final_fallback:  <criterion>                // must yield a total ordering
  },

  // ── Game results ────────────────────────────────────  08_game-results.md
  finalization_rule: {
    require_box_score_sum: <POLICY — O5: boolean>,
    tolerance_points:      <POLICY — O5: int | null>,
    on_mismatch:           <POLICY — O5: 'block' | 'warn' | 'allow'>
  },

  forfeit_rule: {
    counts_as:        <POLICY — O2: 'win_loss' | 'no_contest'>,
    awarded_score:    <POLICY — O2: [int, int] | null>,
    player_stats:     <POLICY — O2: 'none' | 'preserved'>,
    affects_tiebreak: <POLICY — O2: boolean>
  },

  // ── Statistics ──────────────────────────────────────  07_statistics.md
  stats: {
    track_attempts:            <boolean>,       // false ⇒ percentages are NULL, not 0
    min_games_for_leaderboard: <int>,
    composite_metrics: [
      { key: <string>, display_name: <string>,
        formula: <POLICY — O1>, decimals: <int> }
    ]
  },

  // ── Rosters and eligibility ─────────────────────────  12_registration.md
  roster: {
    max_players_per_team: <int | null>,
    roster_lock_date:     <POLICY — O6: date | null>,
    multi_team_allowed:   <POLICY — O6: boolean>,
    fill_ins_allowed:     <boolean>             // FACT: they already happen
  },

  eligibility: {
    minimum_age:             <int>,
    guardian_required_under: <int>,
    age_as_of_date:          <date>             // never "today"
  },

  // ── Scheduling ──────────────────────────────────────  10_scheduling.md
  schedule: {
    format:             'round_robin' | 'double_round_robin' | 'custom',
    games_per_team:     <int>,
    objective_priority: [ <POLICY — O8: ordered objective keys> ],
    timezone:           <IANA zone>             // O9 recommendation
  },

  // ── Playoffs ────────────────────────────────────────  11_playoffs.md
  playoffs: {
    format: {
      type:            'single_elimination' | 'double_elimination' | 'group_then_bracket',
      team_count:      <int>,
      seeding_pattern: '1v8' | '1v8_reseed' | 'custom',
      byes:            <int>,
      series_length:   <int>,
      home_court_rule: <config>
    },
    seed_durability: <POLICY — O4: 'durable' | 'reseed' | 'snapshot'>
  },

  // ── Display ─────────────────────────────────────────
  display: {
    division_noun: <string>       // S13 — "Conference" in copy, division in the model
  }
}
```

---

## 6. Defaults and the ones that must not have them

**Safe to default:** anything where a wrong value is visible and harmless —
decimal places, display nouns, leaderboard minimums.

**REQUIREMENT — must not default:**

| Setting | Why a default is dangerous |
|---|---|
| `tiebreak.*` chains | A silent default decides who makes the playoffs |
| `forfeit_rule` | Silently converts a real outcome into a win or a nothing |
| `finalization_rule` | Decides whether the league's own history is acceptable |
| `eligibility.age_as_of_date` | Changes who is allowed to play |
| `composite_metrics.formula` | Decides an award by an unpublished rule |
| `playoffs.seed_durability` | Decides whether a team's announced seed can move |

**REQUIREMENT.** These are **required keys**. A season cannot activate without
them, and the activation error names which are missing. Defaulting them would
convert every open decision in `20_decisions.md` into a silent one — which is
precisely the failure this specification is built to prevent.

---

## 7. Deployment configuration — separate concern

Bindings, database ids, and secrets are **not** `season.config` and are covered
in `17_operations.md`.

**REQUIREMENT (S28).** Staging and production credentials are fully separated.
**Zero credentials in source, commits, client code, or logs** — a standing
constraint, not a recommendation.

---

## 8. Acceptance tests

| Test | Asserts |
|---|---|
| `config.schema-validated` | An invalid config is rejected at write |
| `config.activation-requires-complete` | A season with missing required keys cannot activate |
| `config.activation-error-names-missing` | The rejection lists the missing keys |
| `config.no-silent-defaults` | Every setting in §6 fails loudly when absent |
| `config.versioned` | Every write produces a new version |
| `config.version-stamped-on-output` | Standings, seeds and brackets record their config version |
| `config.season-scoped` | Editing a template does not alter a running season |
| `config.no-invariant-toggles` | No config key can disable a database-level invariant |
| `config.no-secrets` | No credential appears in `season.config` |
