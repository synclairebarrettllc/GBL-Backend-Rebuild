# 02 — Domain Model

Entities, identity, relationships and lifecycle. This is the vocabulary every
other document uses.

**Scope note.** Officials, payments, expenses, messaging, free agents, reports,
announcements, highlights and player-of-week are **out of scope** (`20_decisions.md`
D-list). They do not appear here, and their absence is deliberate, not an
oversight.

---

## Identity rules — apply to every entity

**REQUIREMENT.** Every entity has an immutable surrogate primary key. It is
assigned once, never reused, never edited, and never carries meaning.

**REQUIREMENT.** No natural key — name, jersey number, email — is ever a primary
key, a foreign key target, or a join condition for identity.

**Evidence (FACT):** the legacy importer matched players by name. K-Town Warriors
field two players both called "0". They collapsed into one record, and because
the stat upsert keys on `(player_id, game_id)`, the second person's line
**overwrote** the first in every shared game — 17 and 4 points became 7. A second
run remapped people again, turning one person's 4 games into two records holding
4 and 5 lines.

**REQUIREMENT.** Identity is never reassigned by tooling. Legacy season creation
issued `UPDATE teams SET season_id = ?`, which moved real teams between seasons
as a side effect of creating a new one **(FACT, `src/index.tsx:2082`)**. Moving
an entity between parents is a modelled operation or it is impossible.

---

## Entity catalogue

### League

The operating organisation. GBL is one league.

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | immutable |
| `name` | text | display only |
| `slug` | text, unique | stable URL identity |

**Relationships:** one League has many Seasons, many Sponsors, one
LeagueConfiguration.
**Lifecycle:** none. A league is not deleted.
**RECOMMENDATION:** model League explicitly even though there is one today.
Multi-tenancy is deferred (D7), but a `league_id` foreign key costs nothing now
and is expensive to retrofit. This is a boundary, not a feature.

---

### Season

A bounded competition with its own rules. **The unit of configuration.**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `league_id` | FK → League | |
| `name` | text | "GBL Season 4" |
| `starts_on`, `ends_on` | date | |
| `timezone` | IANA text | see O9; a season's dates are interpreted in its own timezone |
| `status` | enum | see `04_state-machines.md` |
| `config` | SeasonConfiguration | see `13_configuration.md` |

**Identity of "current":** exactly one Season per League may be `active`.

**REQUIREMENT — one flag, not two.** Season currency is expressed by `status`
alone. There is no second boolean.

**Evidence (FACT):** legacy carried both `seasons.status` and
`seasons.is_active` — 16 query sites read one, 5 the other, nothing kept them
consistent, and the previous season stayed `is_active = 1` forever, leaking two
"active" seasons onto public pages.

**Enforcement:** partial unique index — at most one `status = 'active'` row per
league. The database refuses a second regardless of code path.

---

### Division

An internal grouping within a Season.

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `season_id` | FK → Season | divisions belong to a season, not a league |
| `name` | text | |
| `display_label` | text | **"Conference"** publicly, if configured |

**Evidence / product (S13):** GBL markets **one league with two conferences** and
models it internally as **two divisions**. The domain has one concept; the label
is presentation. `display_label` lives here rather than the domain forcing the
word "division" onto the public site.

**REQUIREMENT.** Division membership is scoped to a Season. A team's division may
differ between seasons without rewriting history.

---

### Person

A human being. **Stable across seasons, teams and name changes.**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | the durable human identity |
| `display_name` | text | **mutable attribute, never identity** |
| `date_of_birth` | date, nullable | required at registration (S10, age verification) |
| `email`, `phone` | text, nullable | contact; not identity |
| `emergency_contact` | text, nullable | captured at registration |

**Why Person and Player are separate.** A Person plays across multiple seasons
and may change teams or name. Collapsing them means either duplicating a human
per season or mutating a shared row when they transfer — the second is how
historical statistics get reattached to the wrong person.

**Same-name handling (REQUIREMENT).** Two Persons may share a `display_name`
without restriction. The system must never merge on name, warn on name, or treat
name collision as an error. **Evidence (FACT):** real GBL rosters contain two
players called "0", two called "11", two called "Alex", and two called "Ron".

---

### Player

A Person's participation in a Season. **The unit statistics attach to.**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `person_id` | FK → Person | |
| `season_id` | FK → Season | |
| `jersey_number` | int, nullable | may duplicate; see below |
| `status` | enum | see state machines |

**Uniqueness:** one Player per `(person_id, season_id)`.

**Jersey numbers are not unique (REQUIREMENT).** The legacy system enforced
uniqueness per team; the real source permits duplicates, and the importer had to
**discard the number to keep the player** when a conflict arose **(FACT)**.
Rejecting a real roster to satisfy an invented constraint is the wrong trade.
Duplicate numbers on one roster are permitted and may be surfaced as a warning.

**Stat lines reference Player, not Person** — so a transfer mid-season does not
retroactively move last month's points.

---

### RosterMembership

A time-scoped relationship between Player and Team.

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `player_id` | FK → Player | |
| `team_id` | FK → Team | |
| `effective_from` | date | |
| `effective_to` | date, nullable | null = current |
| `role` | enum | `player`, `captain` — captain is a label in v1; permissions are D6 |

**Why time-scoped.** Mid-season roster edits are a v1 must-have (S24), and a
player may move teams. A membership row with a date range answers "who was on
this team when this game was played" — a plain `team_id` on Player cannot.

**Fill-ins are real (FACT).** Two legacy players rostered on The Clippers appear
in a Kings box score on 2026-06-13. The current model has no way to express that.

**POLICY — O6.** Whether a Player may hold overlapping memberships (two teams at
once), whether a roster lock date exists, and what happens to statistics on
transfer are **policy decisions**. The schema permits overlap; the domain service
enforces whatever O6 decides. The enforcement point is specified; the rule is not.

---

### Venue

A physical location with scheduling capacity.

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `league_id` | FK → League | |
| `name` | text | |
| `court_count` | int, default 1 | |

**REQUIREMENT.** Venue is a first-class entity, not free text. S22 requires the
scheduler to **error on double-booking a court/time slot**, which is not
expressible against a text field.

**Evidence (FACT):** legacy stored `games.venue` as free text and had no venue
constraint in the scheduler.

---

### Game

A scheduled competition between two Teams. **The container, not the result.**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `season_id` | FK → Season | |
| `home_team_id`, `away_team_id` | FK → Team | must differ |
| `venue_id` | FK → Venue, nullable | |
| `court` | int, nullable | |
| `starts_at` | timestamp (UTC instant) | |
| `status` | enum | see state machines |
| `external_ref` | text, nullable, unique | reserved for import (D1) |

**Game does not carry a score.** The result is a separate concept with its own
authority and lifecycle — see GameResult. Legacy put `home_score`/`away_score`
directly on `games` with a default of `0`, which makes "not yet played" and
"0-0 final" indistinguishable **(FACT — the legacy code carries a comment
documenting exactly this ambiguity)**.

---

### GameResult

The authoritative outcome of a Game. **One per Game, created when the game is
first scored.**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `game_id` | FK → Game, unique | |
| `home_score`, `away_score` | int, ≥ 0 | |
| `result_source` | enum | `derived` \| `entered` |
| `finalized_at` | timestamp, nullable | |

**`result_source` is the central design decision here.**

- **`derived`** — the score is computed from stat lines. Stat lines are
  authoritative; the score is a materialised projection of them.
- **`entered`** — the score was recorded directly with no box score. The score is
  authoritative and stat lines may be absent or partial.

**Why both exist.** S3 makes live stat tracking core, which produces `derived`
results. But a game may be played with no scorekeeper present, and a score-only
record must remain expressible. **Evidence (FACT):** 13 legacy games have box
scores that do not sum to their own posted score, and 3 games have no score at
all — so both modes exist in the real data.

**REQUIREMENT.** `result_source` is set by the mutation that creates the result
and is never inferred. A `derived` result may not be edited directly — correct
the stat lines. An `entered` result may not be silently converted to `derived`.

**POLICY — O5.** Whether a `derived` result requires player points to sum
exactly to the team score before finalisation is policy. The validation hook is
specified in `08_game-results.md`; the rule is a typed empty slot.

---

### PlayerGameStatLine

One player's statistical record in one game. **PRESERVE — the strongest legacy
concept.**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `game_id` | FK → Game | |
| `player_id` | FK → Player | |
| `team_id` | FK → Team | the team they played **for in this game** |
| `two_pointers_made` | int ≥ 0 | |
| `three_pointers_made` | int ≥ 0 | |
| `free_throws_made` | int ≥ 0 | |
| `offensive_rebounds`, `defensive_rebounds` | int ≥ 0 | |
| `assists`, `steals`, `blocks`, `turnovers`, `personal_fouls` | int ≥ 0 | |
| `plus_minus` | int, nullable | S8 |

**Uniqueness:** one line per `(game_id, player_id)`.

**`team_id` is stored on the line, not inferred from the roster.** This is what
makes a fill-in representable — the Clippers players who appeared for the Kings
get a line whose `team_id` is the Kings.

**Scoring is stored as 2PM/3PM/FTM and everything else is derived.**

**Evidence (FACT):** legacy asked for FGM, which silently includes threes. A
scorekeeper entering "3 twos and 2 threes" as FGM=3, 3PM=2 produced **8 points
instead of 12**. Separately, validation required FGA — a statistic this league
does not collect — so `0` read as "zero attempts" rather than "not tracked" and
**every real stat line was rejected**.

**REQUIREMENT.** `points`, `field_goals_made` and `total_rebounds` are **derived,
never stored as independent inputs**:

```
points            = 2·two_pointers_made + 3·three_pointers_made + free_throws_made
field_goals_made  = two_pointers_made + three_pointers_made
total_rebounds    = offensive_rebounds + defensive_rebounds
```

This makes the legacy error **unrepresentable** rather than validated against.
See `07_statistics.md` for attempts, percentages and composite metrics.

---

### Standings — projection, not an entity

**REQUIREMENT.** Standings are computed from finalised GameResults. They are
never accumulated, never hand-edited, and have exactly one writer.

**Evidence (FACT):** four legacy routes each did their own `wins + 1` / `- 1`
bookkeeping. Two drift paths were confirmed live — reversing a completed game
left its win counted forever, and re-completing it added a second.

Whether standings are cached is an implementation choice (`09_standings.md`). If
cached, the cache has one writer and a recompute path, and equality with fresh
recomputation is an automated test.

---

### PlayoffSeed

A team's qualification and rank for a Season's playoffs.

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `season_id` | FK → Season | |
| `team_id` | FK → Team | |
| `seed` | int ≥ 1 | |
| `basis_snapshot` | JSON | the standings rows this seed was computed from |
| `finalized_at` | timestamp | |

**Why `basis_snapshot` (INFERENCE).** Seeds derive from standings, which derive
from games. If a result is corrected after seeding and the seed was never
persisted with its basis, the bracket's original justification is unrecoverable
and "who should have been seeded where" becomes unanswerable.

**POLICY — O4.** Whether a correction reseeds the bracket, leaves it durable, or
something else is policy. **RECOMMENDATION:** durable seed plus basis snapshot.
The field exists so the decision is implementable either way.

---

### Bracket and BracketMatch

**BUILD FRESH.** Progression is structural, never inferred from labels.

**Bracket**

| Field | Type |
|---|---|
| `id` | surrogate |
| `season_id` | FK → Season, unique |
| `format` | enum — driven by season config (S21) |
| `status` | enum |

**BracketMatch**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `bracket_id` | FK → Bracket | |
| `round` | int | 1 = first round; ordinal, not a label |
| `position` | int | slot within the round |
| `home_source` | SlotSource | see below |
| `away_source` | SlotSource | |
| `home_team_id`, `away_team_id` | FK → Team, nullable | resolved once known |
| `winner_advances_to_match_id` | FK → BracketMatch, nullable | **the progression edge** |
| `winner_advances_to_slot` | enum `home` \| `away` | |
| `status` | enum | |

**SlotSource** is either `{type: 'seed', seed: n}` or
`{type: 'winner_of', match_id: n}`.

**Evidence (FACT):** legacy `playoff_games` has **no** `next_game_id`,
`winner_id`, `seed` or `bracket_position` column. The tournament tree existed
only in the reader's head, and "playoff series counting" had to be fixed across
24 separate sites because series logic was scattered wherever someone needed it.

**Series support (REQUIREMENT).** The live legacy bracket is a **two-game series**
per matchup with home/away swapped **(FACT — 14 rows in that shape)**. A
BracketMatch therefore represents a **matchup**, and the Games belonging to it are
linked by `bracket_match_id` on Game. A matchup's winner is decided by
season-configured series rules.

**Format and series length are configuration** (S21, `13_configuration.md` §5):
the structure above expresses any of them without change. **Seeding rules remain
POLICY — O3** (multi-team ties) **and O4** (seed durability after a correction).

---

### Registration

A prospective player's submission to join a Season. **In scope (S10).**

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `season_id` | FK → Season | |
| `person_id` | FK → Person, nullable | linked on acceptance |
| `submitted_name`, `email`, `phone` | text | as entered |
| `date_of_birth` | date | age verification (S10) |
| `emergency_contact` | text | |
| `waiver_signature_ref` | text, nullable | external artefact reference — see O11 |
| `assigned_team_id` | FK → Team, nullable | |
| `status` | enum | see state machines |

**REQUIREMENT.** Registration does **not** capture payment status (S10, S11).

**POLICY — O11.** The waiver vendor is undecided. `waiver_signature_ref` holds
an opaque external reference; its shape is deliberately unspecified.

---

### Sponsor

| Field | Type | Notes |
|---|---|---|
| `id` | surrogate | |
| `league_id` | FK → League | |
| `name` | text | |
| `asset_ref` | text | image or text asset |
| `placement` | text | admin-adjustable (S16) |

**In scope as a data model only.** Display is not a v1 priority. Present so it is
not a retrofit.

---

### SystemEvent

Operational events that must not fail silently (S26).

| Field | Type |
|---|---|
| `id` | surrogate |
| `occurred_at` | timestamp |
| `severity` | enum |
| `category` | text |
| `message` | text |
| `context` | JSON |

**This is not an audit log.** S25 establishes that corrections are simple
overwrites with **no change-log trail on the website**. SystemEvent records
operational failures for the admin dashboard — an import error, a failed
derivation, a rejected deploy — not who changed what.

See `20_decisions.md` for the flagged tension between S25 and the anonymous
tracker write surface.

---

## Relationship summary

```
League ─┬─ Season ─┬─ Division
        │          ├─ Team ─── RosterMembership ─── Player ─── Person
        │          ├─ Game ─┬─ GameResult
        │          │        └─ PlayerGameStatLine
        │          ├─ Registration
        │          ├─ PlayoffSeed
        │          └─ Bracket ─── BracketMatch ──┐
        │                              ▲          │
        │                              └──────────┘  winner_advances_to
        ├─ Venue
        └─ Sponsor
```

Standings do not appear — they are a projection of GameResult, not a stored
entity with independent identity.

---

## What is deliberately absent

| Concept | Why |
|---|---|
| Officials / referees | S18 — deferred by explicit decision |
| Payments, expenses | S11, D9 |
| Announcements, highlights, player-of-week, messaging, free agents, reports | Cut |
| Audit / change-log entity | S25 — explicitly not required |
| `player_season_stats`, `team_game_stats` tables | Legacy tables with 0 rows and 11 code references (FACT). Season and team aggregates are projections |
| `players.season_*`, `games_played` columns | Written on every save, read by nothing, already drifting on 3 players (FACT) |
