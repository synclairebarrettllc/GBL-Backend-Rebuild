# 05 — Database Contract

The schema a builder implements. Types are given in SQLite/D1 terms (the working
default per O7); the constraints are portable and are the actual requirement.

**Reading rule.** Every constraint here exists because its absence caused a
verified failure, or because it enforces a rule from `03_source-of-truth.md`.
Where a constraint is merely conventional, it says so.

---

## What the database enforces vs the service

**Principle:** put a rule in the database when the database can express it
completely. Put it in the service when the rule needs context the database lacks.
**Never put it only in the UI.**

| Enforced by database | Enforced by service |
|---|---|
| Status vocabularies (`CHECK`) | Legal state *transitions* |
| One active season per league (partial unique) | Which season to activate |
| Referential integrity | Cascade *policy* decisions |
| One stat line per (game, player) | Whether the line is basketball-valid |
| Non-negative counting stats | Whether points sum to the team score (**O5**) |
| One result per game | Whether a result may be finalised |
| Unique external refs | Identity matching strategy |
| Seed uniqueness per season | Seeding rules and seed durability (**O3**, **O4**) |

**The reason this table matters (FACT):** `games.status` had a `CHECK` and the
bad write failed loudly. `playoff_games.status` had none and drifted silently for
months. Enforcement placement decided whether a bug took seconds or months to
find.

---

## Conventions

- Primary keys: `INTEGER PRIMARY KEY AUTOINCREMENT`. **`AUTOINCREMENT` is
  required, not optional** — it prevents rowid reuse after deletion, which would
  otherwise let a new entity inherit a deleted one's identity.
- Timestamps: `TEXT` ISO-8601 **UTC instants**. Local time is derived using
  `season.timezone` (O9). Legacy stored mixed formats and rendered every game
  under "Invalid Date" (FACT).
- Booleans: `INTEGER` 0/1 with `CHECK (col IN (0,1))`.
- Money: none. Payments are out of scope (S11).
- Every table has `created_at`; mutable tables have `updated_at`.

---

## Cascade policy — read before writing any foreign key

**REQUIREMENT.** No foreign key referencing an entity that owns gameplay history
may use `ON DELETE CASCADE`.

**Evidence (FACT).** Four tables cascaded off `games`. Schedule regeneration ran
an unconditional `DELETE FROM games WHERE season_id = ?` and destroyed a
completed game together with its entire box score — reproduced as real data loss.
Separately, player delete was a hard `DELETE` and `player_game_stats` cascaded on
`player_id`, erasing lines on games that were actually played.

**Policy:**

| Relationship | On delete | Why |
|---|---|---|
| `player_game_stat_line` → `game` | `RESTRICT` | a game with stats cannot be deleted; archive it |
| `player_game_stat_line` → `player` | `RESTRICT` | history outlives roster membership |
| `game_result` → `game` | `CASCADE` | a result has no meaning without its game, and carries no independent history |
| `game` → `season` | `RESTRICT` | deleting a season must not silently delete its games |
| `roster_membership` → `player`/`team` | `RESTRICT` | |
| `bracket_match` → `bracket` | `CASCADE` | structure is meaningless without its bracket |
| `bracket_match.winner_advances_to_match_id` | `SET NULL` | self-reference; never cascade |
| `registration` → `season` | `RESTRICT` | |

**Soft delete** applies to `game` (`deleted_at`) and `person`/`player`
(`deleted_at`). **REQUIREMENT:** every read filters `deleted_at IS NULL` unless
it is explicitly a historical or administrative query. In the legacy system this
had to be applied across **57 of 62 read sites** and the five exceptions were
deliberate (FACT) — the same discipline applies here from the start.

---

## Tables

### `league`

```sql
CREATE TABLE league (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT NOT NULL,
  slug       TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### `season`

```sql
CREATE TABLE season (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  league_id  INTEGER NOT NULL REFERENCES league(id) ON DELETE RESTRICT,
  name       TEXT NOT NULL,
  starts_on  TEXT NOT NULL,
  ends_on    TEXT NOT NULL,
  timezone   TEXT NOT NULL,                    -- IANA, e.g. 'America/Los_Angeles'
  status     TEXT NOT NULL DEFAULT 'draft'
             CHECK (status IN ('draft','active','completed','cancelled','archived')),
  config     TEXT NOT NULL DEFAULT '{}',       -- SeasonConfiguration JSON
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT,
  CHECK (ends_on >= starts_on)
);

-- THE single-active-season guarantee. Not a convention: the database refuses.
CREATE UNIQUE INDEX ux_season_one_active
  ON season(league_id) WHERE status = 'active';
```

**This index replaces the legacy two-flag design outright.** There is no
`is_active` column, so no second representation can disagree with the first.

### `division`

```sql
CREATE TABLE division (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id     INTEGER NOT NULL REFERENCES season(id) ON DELETE RESTRICT,
  name          TEXT NOT NULL,
  display_label TEXT,                          -- 'Conference' when marketed so (S13)
  sort_order    INTEGER NOT NULL DEFAULT 0,
  UNIQUE (season_id, name)
);
```

### `team`

```sql
CREATE TABLE team (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id    INTEGER NOT NULL REFERENCES season(id) ON DELETE RESTRICT,
  division_id  INTEGER REFERENCES division(id) ON DELETE SET NULL,
  name         TEXT NOT NULL,
  abbreviation TEXT,
  color        TEXT,
  logo_ref     TEXT,
  external_ref TEXT,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (season_id, name)
);
CREATE UNIQUE INDEX ux_team_external_ref ON team(external_ref) WHERE external_ref IS NOT NULL;
```

**REQUIREMENT.** `season_id` is set at creation and **never updated**. Legacy
season creation issued `UPDATE teams SET season_id = ?` and drained real teams
out of the live season on every E2E run (FACT). Moving a team between seasons is
not a supported operation; create a new team.

### `person`

```sql
CREATE TABLE person (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  display_name      TEXT NOT NULL,
  date_of_birth     TEXT,
  email             TEXT,
  phone             TEXT,
  emergency_contact TEXT,
  deleted_at        TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT
);
CREATE INDEX ix_person_name ON person(display_name);   -- search only, NOT identity
```

**No unique constraint on `display_name`.** Two people may share a name. The
index exists for search and must never be used to match identity.

### `player`

```sql
CREATE TABLE player (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id     INTEGER NOT NULL REFERENCES person(id) ON DELETE RESTRICT,
  season_id     INTEGER NOT NULL REFERENCES season(id) ON DELETE RESTRICT,
  jersey_number INTEGER,
  status        TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','inactive')),
  external_ref  TEXT,
  deleted_at    TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (person_id, season_id)
);
CREATE UNIQUE INDEX ux_player_external_ref ON player(external_ref) WHERE external_ref IS NOT NULL;
```

**No uniqueness on `jersey_number`.** Real rosters contain duplicates, and the
legacy importer had to discard the number to keep the player (FACT). Duplicates
are surfaced as a warning, never rejected.

### `roster_membership`

```sql
CREATE TABLE roster_membership (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id      INTEGER NOT NULL REFERENCES player(id) ON DELETE RESTRICT,
  team_id        INTEGER NOT NULL REFERENCES team(id)   ON DELETE RESTRICT,
  effective_from TEXT NOT NULL,
  effective_to   TEXT,
  role           TEXT NOT NULL DEFAULT 'player' CHECK (role IN ('player','captain')),
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE INDEX ix_roster_current ON roster_membership(team_id) WHERE effective_to IS NULL;
CREATE INDEX ix_roster_player  ON roster_membership(player_id);
```

**UNKNOWN — O6.** Whether overlapping open memberships are legal is policy. The
schema permits them; if O6 forbids it, add:
`CREATE UNIQUE INDEX ux_roster_one_open ON roster_membership(player_id) WHERE effective_to IS NULL;`
That one line is the entire implementation difference — deliberately isolated.

### `venue`

```sql
CREATE TABLE venue (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  league_id   INTEGER NOT NULL REFERENCES league(id) ON DELETE RESTRICT,
  name        TEXT NOT NULL,
  court_count INTEGER NOT NULL DEFAULT 1 CHECK (court_count >= 1),
  UNIQUE (league_id, name)
);
```

### `game`

```sql
CREATE TABLE game (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id        INTEGER NOT NULL REFERENCES season(id) ON DELETE RESTRICT,
  home_team_id     INTEGER NOT NULL REFERENCES team(id)  ON DELETE RESTRICT,
  away_team_id     INTEGER NOT NULL REFERENCES team(id)  ON DELETE RESTRICT,
  venue_id         INTEGER REFERENCES venue(id) ON DELETE SET NULL,
  court            INTEGER,
  starts_at        TEXT NOT NULL,                 -- UTC instant
  status           TEXT NOT NULL DEFAULT 'scheduled'
                   CHECK (status IN ('scheduled','in_progress','completed','finalized',
                                     'cancelled','forfeited','void')),
  bracket_match_id INTEGER REFERENCES bracket_match(id) ON DELETE SET NULL,
  external_ref     TEXT,
  deleted_at       TEXT,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT,
  CHECK (home_team_id <> away_team_id)
);
CREATE UNIQUE INDEX ux_game_external_ref ON game(external_ref) WHERE external_ref IS NOT NULL;
CREATE INDEX ix_game_season_time ON game(season_id, starts_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_game_team_home   ON game(home_team_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_game_team_away   ON game(away_team_id) WHERE deleted_at IS NULL;

-- S22: a court/time slot cannot be double-booked.
CREATE UNIQUE INDEX ux_game_venue_slot
  ON game(venue_id, court, starts_at)
  WHERE deleted_at IS NULL AND venue_id IS NOT NULL AND status <> 'cancelled';
```

**`game` carries no score.** See `game_result`. The legacy design defaulted
`home_score`/`away_score` to `0`, making "not played" and "0-0" indistinguishable
— its own source comments document the problem (FACT).

**S22's second rule — a team twice in one day — is not expressible as a unique
index** (it needs a date-range comparison). It is enforced by ScheduleService and
tested by `schedule.no-team-double-book`. That split is deliberate and recorded
here so nobody assumes the database covers it.

### `game_result`

```sql
CREATE TABLE game_result (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id       INTEGER NOT NULL UNIQUE REFERENCES game(id) ON DELETE CASCADE,
  home_score    INTEGER NOT NULL CHECK (home_score >= 0),
  away_score    INTEGER NOT NULL CHECK (away_score >= 0),
  result_source TEXT NOT NULL CHECK (result_source IN ('derived','entered')),
  finalized_at  TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT
);
```

`UNIQUE(game_id)` is the structural guarantee that one game has one result. It is
also what makes "three routes writing a score" impossible to reintroduce as
*different rows*; `03_source-of-truth.md` makes it impossible as different
*writers*.

### `player_game_stat_line`

```sql
CREATE TABLE player_game_stat_line (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id             INTEGER NOT NULL REFERENCES game(id)   ON DELETE RESTRICT,
  player_id           INTEGER NOT NULL REFERENCES player(id) ON DELETE RESTRICT,
  team_id             INTEGER NOT NULL REFERENCES team(id)   ON DELETE RESTRICT,

  two_pointers_made   INTEGER NOT NULL DEFAULT 0 CHECK (two_pointers_made   >= 0),
  three_pointers_made INTEGER NOT NULL DEFAULT 0 CHECK (three_pointers_made >= 0),
  free_throws_made    INTEGER NOT NULL DEFAULT 0 CHECK (free_throws_made    >= 0),

  two_pointers_attempted   INTEGER CHECK (two_pointers_attempted   IS NULL OR two_pointers_attempted   >= two_pointers_made),
  three_pointers_attempted INTEGER CHECK (three_pointers_attempted IS NULL OR three_pointers_attempted >= three_pointers_made),
  free_throws_attempted    INTEGER CHECK (free_throws_attempted    IS NULL OR free_throws_attempted    >= free_throws_made),

  offensive_rebounds  INTEGER NOT NULL DEFAULT 0 CHECK (offensive_rebounds >= 0),
  defensive_rebounds  INTEGER NOT NULL DEFAULT 0 CHECK (defensive_rebounds >= 0),
  assists             INTEGER NOT NULL DEFAULT 0 CHECK (assists        >= 0),
  steals              INTEGER NOT NULL DEFAULT 0 CHECK (steals         >= 0),
  blocks              INTEGER NOT NULL DEFAULT 0 CHECK (blocks         >= 0),
  turnovers           INTEGER NOT NULL DEFAULT 0 CHECK (turnovers      >= 0),
  personal_fouls      INTEGER NOT NULL DEFAULT 0 CHECK (personal_fouls >= 0),
  plus_minus          INTEGER,

  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT,
  UNIQUE (game_id, player_id)
);
CREATE INDEX ix_stat_game   ON player_game_stat_line(game_id);
CREATE INDEX ix_stat_player ON player_game_stat_line(player_id);
```

**Three deliberate decisions, each answering a verified failure:**

1. **No `points`, `field_goals_made` or `total_rebounds` columns.** They are
   derived. Storing them permits disagreement with their own inputs — which is
   exactly what `players.season_*` did, drifting on 3 players (FACT).

2. **Makes are `NOT NULL DEFAULT 0`; attempts are `NULL`-able.** GBL records
   makes. `NULL` attempts mean *not tracked*; `0` means *zero attempts*. Legacy
   conflated them and **rejected every real stat line** (FACT).

3. **Attempts are constrained relative to makes only when present.** `made > attempted`
   is impossible; "attempted not recorded" is legal.

**The 8-instead-of-12 bug is now unrepresentable.** There is no combined-makes
field to misinterpret.

### `playoff_seed`

```sql
CREATE TABLE playoff_seed (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id      INTEGER NOT NULL REFERENCES season(id) ON DELETE RESTRICT,
  team_id        INTEGER NOT NULL REFERENCES team(id)   ON DELETE RESTRICT,
  seed           INTEGER NOT NULL CHECK (seed >= 1),
  basis_snapshot TEXT NOT NULL,                 -- standings rows used, JSON
  finalized_at   TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (season_id, seed),
  UNIQUE (season_id, team_id)
);
```

Both unique constraints matter: one team cannot hold two seeds, and one seed
cannot be held by two teams.

### `bracket` and `bracket_match`

```sql
CREATE TABLE bracket (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id  INTEGER NOT NULL UNIQUE REFERENCES season(id) ON DELETE RESTRICT,
  format     TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'draft'
             CHECK (status IN ('draft','seeded','in_progress','completed')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE bracket_match (
  id                        INTEGER PRIMARY KEY AUTOINCREMENT,
  bracket_id                INTEGER NOT NULL REFERENCES bracket(id) ON DELETE CASCADE,
  round                     INTEGER NOT NULL CHECK (round >= 1),
  position                  INTEGER NOT NULL CHECK (position >= 1),

  home_source_type          TEXT NOT NULL CHECK (home_source_type IN ('seed','winner_of')),
  home_source_seed          INTEGER,
  home_source_match_id      INTEGER REFERENCES bracket_match(id) ON DELETE SET NULL,
  away_source_type          TEXT NOT NULL CHECK (away_source_type IN ('seed','winner_of')),
  away_source_seed          INTEGER,
  away_source_match_id      INTEGER REFERENCES bracket_match(id) ON DELETE SET NULL,

  home_team_id              INTEGER REFERENCES team(id) ON DELETE RESTRICT,
  away_team_id              INTEGER REFERENCES team(id) ON DELETE RESTRICT,
  winner_team_id            INTEGER REFERENCES team(id) ON DELETE RESTRICT,

  winner_advances_to_match_id INTEGER REFERENCES bracket_match(id) ON DELETE SET NULL,
  winner_advances_to_slot     TEXT CHECK (winner_advances_to_slot IN ('home','away')),

  status                    TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','ready','in_progress','completed')),
  created_at                TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at                TEXT,
  UNIQUE (bracket_id, round, position),
  CHECK ((home_source_type = 'seed'      AND home_source_seed     IS NOT NULL)
      OR (home_source_type = 'winner_of' AND home_source_match_id IS NOT NULL)),
  CHECK ((away_source_type = 'seed'      AND away_source_seed     IS NOT NULL)
      OR (away_source_type = 'winner_of' AND away_source_match_id IS NOT NULL))
);
```

**`winner_advances_to_match_id` is the whole point.** Progression is a foreign
key. It is not a round name, not a naming convention, not something a reader
reconstructs. Legacy had none of these columns and required fixes across 24 sites
because series logic lived wherever it was needed (FACT).

The paired `CHECK`s make a slot with no resolvable source **impossible to
insert** — a partially specified bracket cannot exist in the database.

### `registration`

```sql
CREATE TABLE registration (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id            INTEGER NOT NULL REFERENCES season(id) ON DELETE RESTRICT,
  person_id            INTEGER REFERENCES person(id) ON DELETE SET NULL,
  submitted_name       TEXT NOT NULL,
  email                TEXT,
  phone                TEXT,
  date_of_birth        TEXT NOT NULL,           -- S10: age verification
  emergency_contact    TEXT,
  waiver_signature_ref TEXT,                    -- O11: opaque external reference
  assigned_team_id     INTEGER REFERENCES team(id) ON DELETE SET NULL,
  status               TEXT NOT NULL DEFAULT 'submitted'
                       CHECK (status IN ('submitted','accepted','assigned','rejected','withdrawn')),
  created_at           TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at           TEXT
);
```

### `sponsor`

```sql
CREATE TABLE sponsor (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  league_id  INTEGER NOT NULL REFERENCES league(id) ON DELETE RESTRICT,
  name       TEXT NOT NULL,
  asset_ref  TEXT,
  placement  TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);
```

### `system_event`

```sql
CREATE TABLE system_event (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL DEFAULT (datetime('now')),
  severity    TEXT NOT NULL CHECK (severity IN ('info','warning','error','critical')),
  category    TEXT NOT NULL,
  message     TEXT NOT NULL,
  context     TEXT
);
CREATE INDEX ix_event_recent ON system_event(occurred_at DESC);
```

**Not an audit log.** S25 establishes that corrections are simple overwrites with
no change-log on the website. This table carries operational failures for the
admin dashboard (S26: nothing fails silently) — not who changed what.

---

## Tables deliberately not created

| Legacy table | Disposition | Why |
|---|---|---|
| `player_season_stats` | **RETIRE** | 0 rows, 4 code references. Season totals are a projection |
| `team_game_stats` | **RETIRE** | 0 rows, 11 code references. Team box scores derive from player lines |
| `players.season_*`, `games_played` | **RETIRE** | Written on every save, read by nothing, drifting on 3 players |
| `payments`, `expenses` | **RETIRE** | Out of scope (S11) |
| `referees`, `referee_assignments` | **DEFER** | S18 |
| `announcements`, `highlights`, `player_of_week`, `broadcast_messages` | **RETIRE** | Cut |
| `admin_logs` | **REPLACE** | Superseded by `system_event`; S25 declines a change-log |
| `users` | **RETIRE** | Never populated; unresolved FK with `expenses.created_by` (FACT) |
| `league_settings` (51 columns) | **REPLACE** | Becomes `season.config` JSON plus league branding. 51 columns is a settings bag, not a schema |

---

## Migration compatibility gate

**REQUIREMENT.** Application code that reads a column may not deploy against a
schema lacking it. Enforced mechanically before deployment
(`17_operations.md`).

**This is not hypothetical (FACT).** It happened twice in production. The first
outage took down the admin schedule; the second took down public leaderboards and
standings **while the league owner was entering live statistics**. Both times the
local check passed, because locally the column already existed.
