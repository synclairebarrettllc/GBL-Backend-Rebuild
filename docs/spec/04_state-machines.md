# 04 — State Machines

Every lifecycle is explicit. No state is inferred from the presence of a value,
the absence of a null, or a label.

**Evidence (FACT).** The legacy system inferred bracket progression from round
names, and wrote `status = 'completed'` while ~45 sites compared against
`'final'` — every one of those comparisons permanently false, silently. It is why
`player_game_stats` was empty for the life of the app.

---

## Canonical status vocabulary

**REQUIREMENT.** These words mean exactly one thing each, across every table.
`final`, `complete`, `finished`, `done` and `closed` are **not synonyms** for
anything and must not appear as status values.

| Word | Meaning |
|---|---|
| `draft` | exists, not yet operative |
| `scheduled` | committed to happen |
| `in_progress` | happening now |
| `completed` | happened, outcome recorded |
| `finalized` | outcome locked; further change requires an explicit correction |
| `cancelled` | will not happen; not counted |
| `forfeited` | did not happen as contested; counted per policy (**POLICY — O2**) |
| `archived` | historical, read-only |
| `void` | created in error; excluded from everything |

**Enforcement (REQUIREMENT).** Every status column carries a `CHECK` constraint
listing its legal values.

**This is the single most load-bearing enforcement rule in the specification.**
`games.status` had a CHECK and the bad write **failed loudly**.
`playoff_games.status` had none and **drifted silently for months** (FACT). Same
bug, same day, opposite outcomes — decided entirely by whether the schema could
say no.

---

## Season

```
draft ──► active ──► completed ──► archived
  │         │
  └────────►└──► cancelled
```

| From | To | Trigger | Actor | Validation | Side effects |
|---|---|---|---|---|---|
| `draft` | `active` | activate season | admin | config valid; **no other active season in league** | previous active season → `completed` |
| `active` | `completed` | close season | admin | all games `finalized`, `cancelled` or `forfeited` | standings frozen |
| `completed` | `archived` | archive | admin | — | read-only |
| `draft`/`active` | `cancelled` | cancel | admin | — | games → `cancelled` |

**Illegal:** `archived` → anything. `completed` → `active` (reopening a season is
not a transition; it is a new season).

**Enforcement:** partial unique index guarantees ≤1 `active` per league **at the
database level**, so a second cannot be created by any code path — including a
future one nobody has written yet.

---

## Game

```
scheduled ──► in_progress ──► completed ──► finalized
    │              │              │
    │              │              └──────► (correction) ──► completed
    ├──► cancelled │
    └──► forfeited ◄──────────────┘
```

| From | To | Trigger | Actor | Validation | Side effects |
|---|---|---|---|---|---|
| `scheduled` | `in_progress` | first stat line written, or explicit start | tracker / admin | game is today or admin override | — |
| `scheduled` | `completed` | result entered directly | admin | valid scores | GameResult created (`entered`) |
| `in_progress` | `completed` | tracker submits, or admin completes | tracker / admin | see O5 | GameResult created/updated (`derived`) |
| `completed` | `finalized` | finalize | admin | **POLICY — O5** completeness rule | standings recomputed; seed eligibility opens |
| `finalized` | `completed` | **correction** | admin | correction permitted (**POLICY — O8-equivalent**) | downstream recompute cascades |
| `scheduled` | `cancelled` | cancel | admin | — | excluded from standings |
| any non-final | `forfeited` | forfeit | admin | **POLICY — O2** | counted per policy |

**Illegal:** `cancelled` → `completed`. `scheduled` → `finalized` (must pass
through `completed`). Any transition that destroys stat lines.

**REQUIREMENT.** `finalized` → `completed` is a **first-class correction**, not a
back door. It is permitted, audited by outcome (standings change), and cascades.
Legacy had `reopen` as a route that set `in_progress` and cleared the lock, with
no defined propagation (FACT).

---

## GameResult

```
(none) ──► provisional ──► final
              │              │
              └──────────────┘  correction
```

`provisional` while the game is `completed`; `final` when the game is
`finalized`. A `derived` result may **never** be edited directly — correct the
stat lines and the result recomputes. An `entered` result is edited through
GameResultService only.

---

## PlayerGameStatLine

Stat lines have no status. They exist or they do not.

**REQUIREMENT.** A stat line is never soft-deleted or flagged. Removing a player
from a box score deletes the line, within the same transaction that recomputes
the result.

**Rationale.** A statistic is not a lifecycle object. Giving it states invites
"deleted but still counted", which is precisely the class of bug this
specification exists to prevent.

**Protection instead comes from the Game.** Stat lines cannot be destroyed by
deleting their container — see `05_database.md` on cascade policy.

---

## RosterMembership

```
active ──► ended
```

Not a rich lifecycle: a membership is open (`effective_to IS NULL`) or closed.
A transfer closes one membership and opens another. **Closing a membership never
touches stat lines** — those reference Player and carry their own `team_id`.

**POLICY — O6.** Whether overlapping open memberships are legal is policy. The
state machine permits it; RosterService enforces whatever O6 decides.

---

## Registration

```
submitted ──► accepted ──► assigned
     │             │
     ├──► rejected │
     └──► withdrawn
```

| From | To | Trigger | Validation |
|---|---|---|---|
| `submitted` | `accepted` | admin accepts | waiver present; age verified (S10) |
| `accepted` | `assigned` | admin assigns team | team has capacity per config |
| `submitted` | `rejected` | admin rejects | — |
| `submitted` | `withdrawn` | registrant withdraws | — |

**On `assigned`:** a Person is created or matched, a Player is created for the
season, and a RosterMembership opens — one transaction.

**REQUIREMENT.** Person matching at acceptance is **operator-confirmed, never
automatic on name**. The system may suggest; it may not merge. This is B4
applied at the point where the temptation is strongest.

---

## Bracket

```
draft ──► seeded ──► in_progress ──► completed
```

| From | To | Trigger | Validation |
|---|---|---|---|
| `draft` | `seeded` | seeds finalised | seed count matches format; `basis_snapshot` written |
| `seeded` | `in_progress` | first match starts | structure complete — every non-first-round slot has a source |
| `in_progress` | `completed` | final match finalised | all matches resolved |

**REQUIREMENT.** Transition to `seeded` requires the **full structure** to exist —
every match, every `winner_advances_to` edge. A partially built bracket is not
seedable. This is what prevents progression-by-label reappearing.

---

## BracketMatch

```
pending ──► ready ──► in_progress ──► completed
                          │              │
                          └──────────────┘  correction
```

- **`pending`** — at least one participant unresolved (its source match has no
  winner yet).
- **`ready`** — both participants resolved; games may be scheduled.
- **`completed`** — series decided per config; winner propagated.

| From | To | Trigger | Side effects |
|---|---|---|---|
| `pending` | `ready` | upstream winner resolved | fills `home_team_id`/`away_team_id` |
| `ready` | `in_progress` | first game starts | — |
| `in_progress` | `completed` | series decided | **propagate winner along `winner_advances_to`** |
| `completed` | `in_progress` | **correction** | recompute winner; re-propagate; **unrelated matches untouched** |

**REQUIREMENT — bounded propagation.** A correction touches only matches
reachable from the corrected one along progression edges. Every other match is
byte-identical afterward. This is a tested invariant
(`bracket.correction-bounded`), not an aspiration.

---

## Import / reconciliation job

Retained for D1 (deferred migration) so the shape exists when needed.

```
pending ──► running ──► completed
                │
                └──► failed ──► running   (resume)
```

Jobs are resumable and replay-safe. A replay of an already-applied dataset
produces **no changes** (`import.replay-noop`).

---

## Cross-cutting rules

**REQUIREMENT.** Every transition is executed by a domain service method. No
route, script, or tool issues an `UPDATE` to a status column directly.

**REQUIREMENT.** Every transition validates its precondition **inside the same
transaction** that performs it. Checking status and then updating it in two
statements is a race, and the legacy code relied on exactly that pattern with a
comment acknowledging it.

**REQUIREMENT.** Illegal transitions are rejected with a typed error naming the
current state, attempted state, and reason. Silent no-ops are prohibited —
they are indistinguishable from success, which is how the dead delete button
survived for months (FACT).

**Test coverage.** Every state machine has a test asserting that every illegal
transition in its table is rejected. Legal-path tests alone are insufficient:
the legacy failures were all in paths nobody tested.
