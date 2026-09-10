# 15 — API Contracts

The API is a thin layer over the domain services. It parses, authorises,
delegates, and serialises. **It contains no domain logic.**

**Evidence for why this is stated as a rule (FACT).** In the legacy system the
domain logic *was* the routes — which is how three routes came to write
`game.home_score` with three different rule sets, and how a single file reached
8,373 lines.

---

## 1. Structural rules

**R-API-1 — routes call services.** No route issues SQL. Static check:
no `INSERT`/`UPDATE`/`DELETE`/`SELECT` outside the data layer
(`06_mutations.md` R5).

**R-API-2 — one endpoint per operation.** If two endpoints can change the same
fact, one of them is a defect. There is no "convenience" variant.

**R-API-3 — read endpoints are projections.** A `GET` never writes, never
lazily creates, and never repairs data it finds inconsistent.

**R-API-4 — every list endpoint filters deleted rows.** See §4.

**R-API-5 — errors are the typed domain errors** from `06_mutations.md` §6,
serialised. Routes do not invent their own error vocabulary.

---

## 2. Surfaces

Three distinct surfaces with three distinct authorisation models
(`16_security.md`).

| Surface | Prefix | Auth | Writes |
|---|---|---|---|
| **Public** | `/api/` | none | none |
| **Admin** | `/api/admin/` | admin session | all |
| **Tracker** | `/api/track/` | per-game capability token | stat lines for **one** game |
| **AI read** | `/api/ai/` | authenticated, read-only (S12) | none |

**REQUIREMENT.** These are separate route trees with separate middleware. A
public endpoint cannot become privileged by adding a parameter, because the
authorisation is attached to the tree, not to the handler.

---

## 3. Resource shapes

### Public player

```
{ id, display_name, jersey_number, team: { id, name },
  season_totals: { games_played, points, rebounds, assists, steals, blocks,
                   turnovers, fg_pct, three_pct, ft_pct },   // fg_pct etc. may be null
  per_game: { ppg, rpg, apg, ... } }
```

**REQUIREMENT.** No `phone`, `email`, `date_of_birth`, `emergency_contact`, or any
registration field. Ever. (`12_registration.md` §8.)

**REQUIREMENT.** Percentages are `null` when attempts are untracked — never `0`
and never `0.000`. Serialisation must not coerce (`07_statistics.md` §1).

### Public game

```
{ id, status, starts_at, venue: { id, name, court },
  home: { team, score }, away: { team, score },
  result_source, box_score?: [ StatLine ] }
```

**REQUIREMENT.** `starts_at` is a UTC instant plus the season timezone, or a
single unambiguous representation — never a pre-formatted display string
(`10_scheduling.md` §2).

### Public standings

```
{ scope, config_version, computed_at,
  rows: [ { rank, team, wins, losses, ties, win_pct, points_for, points_against,
            point_differential, streak,
            tiebreak_note?: "separated from <team> by point_differential" } ] }
```

**REQUIREMENT.** `config_version` is exposed. A standings table that cannot say
which rules produced it is not verifiable, and S9's whole premise is that people
verify these numbers themselves.

---

## 4. The deleted-row discipline

**REQUIREMENT.** Every read of a soft-deletable entity filters `deleted_at IS
NULL`, unless it is an admin view explicitly requesting deleted rows.

**Evidence (FACT) — and why this is a *structural* requirement, not a code
review item.** Adding `deleted_at` to the legacy system required auditing 62 read
sites. The first audit claimed ~40 fixed; the real number was 45, with 17
unfiltered and only 4 of those deliberate — **11 genuinely open, 7 of them
user-visible**. Getting to 57/62 with 5 documented exceptions took a second pass.

A rule enforced by remembering it at 62 call sites will be violated. Therefore:

**REQUIREMENT.** The filter is applied in the **data access layer**, by
construction, for every soft-deletable entity. Including deleted rows requires an
explicit opt-in parameter. The default is safe; the exception is loud.

**REQUIREMENT.** A test enumerates every read path and asserts the filter, so the
count is produced by the suite rather than by an audit.

---

## 5. Endpoint inventory

### Public — read only

```
GET /api/seasons/current
GET /api/seasons/:id
GET /api/teams                       ?season
GET /api/teams/:id
GET /api/teams/:id/roster
GET /api/players                     ?season  ?team  ?sort  ?page
GET /api/players/:id
GET /api/games                       ?season  ?team  ?date  ?status
GET /api/games/:id
GET /api/games/:id/box-score
GET /api/standings                   ?season  ?scope
GET /api/leaderboards                ?season  ?category  ?min_games
GET /api/brackets/:season_id
GET /api/venues
GET /api/sponsors
```

### Tracker — one game, capability token

```
POST   /api/track/:token/start
PUT    /api/track/:token/stat-line          { player_id, team_id, stats, operation_id }
DELETE /api/track/:token/stat-line/:player_id
POST   /api/track/:token/submit
GET    /api/track/:token/state
```

**REQUIREMENT.** The token identifies the game. No endpoint in this tree accepts a
`game_id` parameter — there is nothing to tamper with (`16_security.md`).

### Admin

```
POST/PUT/DELETE  /api/admin/seasons          + /activate  /close
POST/PUT         /api/admin/teams
POST/DELETE      /api/admin/roster-memberships
POST/PUT/DELETE  /api/admin/games
POST             /api/admin/games/:id/result           enterResult
POST             /api/admin/games/:id/finalize
POST             /api/admin/games/:id/correct
PUT/DELETE       /api/admin/games/:id/stat-lines/:player_id
POST             /api/admin/schedule/generate          dry run
POST             /api/admin/schedule/commit
POST             /api/admin/schedule/bulk-reschedule   dry run by default
POST             /api/admin/playoffs/seeds/finalize
POST             /api/admin/playoffs/bracket/generate
GET/POST         /api/admin/registrations              + /accept /reject /assign
GET/PUT          /api/admin/seasons/:id/config
POST             /api/admin/games/:id/tracker-token
GET              /api/admin/dashboard
```

**REQUIREMENT (S26) — the dashboard flags incomplete work.** Games that have been
played but are missing scores or stats appear prominently. **Errors surface
visibly; nothing fails silently.** Game 1971 — five real stat lines, still reading
`scheduled 0-0` — would have appeared here on the day it happened instead of
being found months later in an audit.

### AI read surface (S12)

```
GET /api/ai/**      authenticated, read-only, no embedded chatbot
```

**REQUIREMENT.** This surface returns exactly what the public surface returns.
Authentication controls **access**, not scope — it must not expose PII that the
public API withholds.

---

## 6. Conventions

**Idempotency.** Every mutating endpoint accepts `operation_id`. Replay returns
the original outcome with `200`, never a duplicate (`06_mutations.md` R6).

**Pagination.** Every collection endpoint paginates with a documented default and
maximum. **FACT:** the legacy `/players` endpoint returned all 264 rows unpaginated
and unfiltered, including 31 players with zero games.

**Status codes.**

| Code | Use |
|---|---|
| `200` | success, including idempotent replay |
| `201` | resource created |
| `400` | malformed request |
| `401` / `403` | unauthenticated / unauthorised |
| `404` | not found, **or soft-deleted for a non-admin caller** |
| `409` | state conflict — illegal transition, slot taken, deleted upstream |
| `422` | valid shape, failed domain validation |

**REQUIREMENT.** A `409` is never a partial success. Its body carries the typed
error, and a client must check the status before reading the body.

**Evidence (FACT):** the legacy importer read `game_id` off a `409` body and
continued as though it had succeeded, failing two steps later with a message that
pointed nowhere near the cause.

**REQUIREMENT — no envelope lying.** No endpoint returns `200` with
`{ success: false }`. The status code is the truth.

---

## 7. Acceptance tests

| Test | Asserts |
|---|---|
| `api.no-sql-in-routes` | Static check: no SQL outside the data layer |
| `api.single-write-path` | No fact is writable by two endpoints |
| `api.get-never-writes` | Every `GET` leaves the database byte-identical |
| `api.deleted-filtered-everywhere` | Every read path excludes soft-deleted rows by default |
| `api.no-pii-public` | No public or AI response contains a registration field |
| `api.null-percentages` | Untracked attempts serialise as `null`, not `0` |
| `api.tracker-no-game-param` | No tracker endpoint accepts a game id |
| `api.status-codes-truthful` | No `200` carries a failure body |
| `api.idempotent-replay` | Replay returns the original outcome, creates nothing |
| `api.pagination-enforced` | No collection endpoint returns unbounded rows |
| `api.error-shape` | Every error matches the typed domain error shape |
| `api.dashboard-flags-incomplete` | A played game missing stats appears on the dashboard |
