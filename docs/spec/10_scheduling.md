# 10 — Scheduling Engine

**Direction: BUILD FRESH.** Legacy had no scheduler — games were rows created by
hand. S21 requires a parameter-driven engine, and S17 requires bulk operations
that legacy could not express at all.

---

## 1. Single source of truth for timing

**REQUIREMENT (S23).** The scheduler owns every time in the system. There are no
parallel clocks — no separate playoff schedule table, no denormalised date on a
bracket match, no second start time on a result.

**Evidence (FACT).** Legacy carried `playoff_games` as a table parallel to
`games`, with its own status column that had no CHECK constraint and drifted
silently for months. Two homes for "when does this game happen" produced two
answers.

**Consequence:** a bracket match does not store a date. It references games, and
the games carry the schedule. See `11_playoffs.md`.

---

## 2. Time representation — O9

**RECOMMENDATION (O9, AUTHORABLE — Board decides):**

- Store instants as **UTC** in a single, consistent format.
- Store the league's local IANA timezone on `season`.
- Derive all display dates from those two facts.
- Never store a formatted date string as data.

**Evidence (FACT).** Legacy stored mixed date formats, and every game rendered
under "Invalid Date" — a total display failure caused entirely by representation,
not by logic.

**REQUIREMENT regardless of the O9 outcome.** One representation, applied
everywhere, validated at write. A date that cannot be parsed is rejected at the
mutation boundary, not discovered by a user.

**Date boundaries matter for real rules.** "One team may not play twice in a day"
(S22) needs a definition of *day*. That is the league's local day, not UTC —
a 9pm game is not tomorrow's game.

---

## 3. Hard constraints — S22

**REQUIREMENT.** These are enforced, not advisory. A schedule violating either is
rejected.

| Constraint | Enforcement |
|---|---|
| **No court/time-slot double-booking** — one game per `(venue, court, start time)` | **Database partial unique index** (`05_database.md`), so no code path can bypass it |
| **No team playing twice in one local day** | Service-level, transactional — expressible as a query, not as a unique index |

**Why the split.** The venue constraint is a property of a single row's columns,
so the database can hold it absolutely. The team-per-day constraint spans two
rows and a timezone conversion, so it lives in `ScheduleService` — and is
therefore checked **inside the transaction** (R2), never as a pre-flight read.

**REQUIREMENT.** Both violations produce typed errors naming **the conflicting
game id**. "Slot unavailable" makes the operator hunt; the id ends the search.

---

## 4. Generation

**REQUIREMENT (S21).** Season structure is a parameter, never hardcoded. Game
counts, weeks, and formats come from config.

```
ScheduleService.generate(season_id, params) → ProposedSchedule
```

```
params = {
  format:            'round_robin' | 'double_round_robin' | 'custom',
  games_per_team:    <int>,
  venues:            [ { venue_id, courts, available_slots } ],
  blackout_dates:    [ <date> ],
  start_date:        <date>,
  weeks:             <int>,
  objective_priority: <UNKNOWN — O8>
}
```

**REQUIREMENT — generation proposes, it does not commit.** `generate()` returns a
proposed schedule plus a constraint report. A separate, explicit
`commitSchedule()` writes games. This is the dry-run discipline from
`06_mutations.md` §5 applied to the highest-volume write in the system.

**REQUIREMENT.** If no valid schedule exists under the constraints, the engine
returns **which constraint could not be satisfied and where** — not an empty
result and not a partial schedule.

### Objective priority — UNKNOWN — O8

S22 fixes the two hard constraints. When many valid schedules exist, what is
optimised — home/away balance, rest days between games, venue fairness,
time-slot fairness (nobody gets every 9pm game) — and **in what order**, is not
decided.

**Typed slot:**

```
objective_priority = [ <UNKNOWN — O8: ordered list of objective keys> ]
```

**Interim behaviour:** the engine satisfies the hard constraints, applies no
optimisation beyond that, and **reports the resulting balance metrics** so an
operator can judge the schedule. It does not silently optimise for something
nobody chose.

---

## 5. Bulk rescheduling — S17

**REQUIREMENT (S17, confirmed v1).** A gym closure is **one atomic admin action**,
not per-game edits.

```
ScheduleService.bulkReschedule(criteria, resolution) → BulkResult
```

- `criteria` — e.g. all games at venue V on date D
- `resolution` — move to a new date/venue, or cancel

**REQUIREMENT — atomic.** All affected games move, or none do. A partial bulk
reschedule is the worst possible outcome: some teams informed, some not, and no
way to tell which is which.

**REQUIREMENT — dry run first.** The default first invocation reports every
affected game and every conflict the move would create, and changes nothing.

**REQUIREMENT — constraints still apply.** A bulk move that would double-book a
court or make a team play twice in a day is rejected **as a whole**, naming every
conflict at once. Fixing conflicts one error at a time across 20 games is not a
usable operation.

### Notification cascade — blocked on G4

Rescheduling implies telling people. **G4 is an unresolved scope conflict:**
Round 2 places email/text notifications in scope; Round 3 states no provider is
built in and communications are handled externally.

**REQUIREMENT.** `bulkReschedule` emits a structured, complete **change set**
— every affected game, both times, both venues, and the affected teams — as part
of its result.

Whether that change set is delivered by an in-app notification subsystem, exported
for external sending, or simply displayed to the operator is **G4's decision**.
The engine produces the payload either way, so the decision changes a consumer,
not the scheduler.

---

## 6. Individual operations

Contracts are in `06_mutations.md` §4.4. In summary:

| Operation | Constraint check | Touches results/stats |
|---|---|---|
| `scheduleGame` | both hard constraints | no |
| `rescheduleGame` | both hard constraints; game not `finalized` | **no** |
| `cancelGame` | game not `finalized` | standings only (game leaves the denominator) |
| `deleteGame` | game has no stat lines | refuses otherwise |

**REQUIREMENT.** Rescheduling changes when and where a game happens. It never
touches who played, what they did, or what the score was. These are different
facts with different owners.

---

## 7. Venues

`venue` is a first-class entity with courts. A game references
`(venue_id, court)`.

**REQUIREMENT.** Court is part of the identity of a slot. A gym with three courts
hosts three simultaneous games, and the unique index reflects that — which is
exactly why the index is on `(venue_id, court, starts_at)` rather than on
`(venue_id, starts_at)`.

**Officials/referees: DEFERRED (S18).** No officials entity is built. **The
scheduler design must not preclude one** — an official is another resource with
availability, which is the same shape as a court. No accommodation beyond that.

---

## 8. What the scheduler never does

| Never | Because |
|---|---|
| Stores a second copy of a game time | S23 — one clock |
| Commits a generated schedule without an explicit second step | Bulk writes need a dry run |
| Partially applies a bulk operation | Half-informed teams are worse than none |
| Silently optimises for an unchosen objective | O8 is open; guessing hides the choice |
| Reschedules a finalized game | The game already happened |
| Stores formatted date strings | "Invalid Date" across the whole site (FACT) |

---

## 9. Acceptance tests

| Test | Asserts |
|---|---|
| `schedule.no-double-book-court` | Two games in one `(venue, court, time)` are rejected by the **database** |
| `schedule.no-team-twice-per-day` | A team's second game in one local day is rejected |
| `schedule.day-boundary-local` | The per-day rule uses league-local days, not UTC |
| `schedule.conflict-names-game` | Conflict errors carry the conflicting game id |
| `schedule.generate-is-dry-run` | `generate()` writes nothing |
| `schedule.generate-reports-infeasible` | An unsatisfiable constraint set names the constraint |
| `schedule.bulk-atomic` | An injected failure mid-bulk leaves zero games moved |
| `schedule.bulk-reports-all-conflicts` | Conflicts are reported together, not one at a time |
| `schedule.bulk-emits-change-set` | The result contains every affected game and both time/venue pairs |
| `schedule.reschedule-preserves-stats` | Moving a game changes no stat line and no result |
| `schedule.no-parallel-clock` | Schema check: no second table stores a game time |
| `schedule.date-round-trip` | Every stored instant parses and renders — no "Invalid Date" |
