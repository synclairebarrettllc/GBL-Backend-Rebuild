# 20 — Decision Register

Two lists. **Settled** decisions come from the Alignment Interview sessions and
Build Governance Rules — they are product authority and must survive into the
specification. **Open** items genuinely block or shape specification work.

**Source authority:** *Backend Rebuild — Alignment Interview Recap* (Notion) is
the authoritative requirements source. This register summarises; it never
replaces it. Where they disagree, the Notion page wins.

> **Correction, 2026-09-09.** An earlier version of this file classified Season 3
> closeout, RecLeague authority and legacy migration as BLOCKING. **That was
> wrong.** The scope reset establishes those as Phase 2 concerns. They are
> reclassified DEFERRED below. The error came from treating the legacy system's
> operational state as a prerequisite for designing a new backend; it is not.

---

## Part 1 — SETTLED (established decision; do not reopen)

### Scope and product

| # | Decision | Source |
|---|---|---|
| S1 | v1 has **exactly one admin** (Synclaire). Captain roster-edit access is a **fast-follow**, not v1 | Interview, Session 4 |
| S2 | Public/player-facing v1 is **view-only** — team stats, player stats, history, records | Interview |
| S3 | **Courtside live stat tracking is core**, not an after-the-fact import | Interview |
| S4 | Stat tracker is an **anonymous tool** — no scorekeeper accounts or logins | Session 4 |
| S5 | Tracker must run on **phone (primary), tablet, laptop** | Session 4 |
| S6 | Stats must be **saved progressively during entry**, not only on submit | Session 4 |
| S7 | **Offline sync / CRDT is DEFERRED.** Tracker assumes live connectivity | Gate G1 closure |
| S8 | Stat depth target is **NBA-caliber**: basics plus shooting percentages plus composite metrics (plus-minus, efficiency) | Interview |
| S9 | Composite stats are **structurally required** — season awards depend on them | Session 4 "why" |
| S10 | **Registration is in scope**: waiver with e-signature, age verification, walk-up mobile registration. Captures name, waiver, team, emergency contact, phone, email. **Not** payment status | Round 2 |
| S11 | **No in-app payments** in v1. Zelle/CashApp posted; Stripe later | Interview |
| S12 | **AI data access**: private, authenticated, **read-only**. No embedded chatbot | Round 2 |
| S13 | Marketed as **one league, two conferences**; modeled internally as **two divisions** | Interview |
| S14 | Scale target: **dozens of teams, many divisions** | Interview |
| S15 | **Multi-tenancy deferred**, not a design driver | Interview |
| S16 | Sponsor **data model support from the start** (image/text, admin-adjustable placement); display is not a v1 priority | Interview |
| S17 | **Bulk operational rescheduling is a confirmed v1 requirement** — one gym closure is one atomic admin action, not per-game edits. Lives inside the Scheduler | Session 9 |
| S18 | **Officials/referees entity: DEFERRED.** Do not block scheduler design on it | Session 9 |
| S19 | Mobile-first across phone, tablet, desktop | Session 4 |

### Rules and engines

| # | Decision | Source |
|---|---|---|
| S20 | Tiebreakers are **admin-configurable and reorderable**, with **different chains for regular season vs playoffs**. **Default: point differential** | Round 3 |
| S21 | Season structure (game counts, playoff format) is **not hardcoded** — scheduler and playoff generator are parameter-driven engines | Interview |
| S22 | Scheduler must **validate and error** on a team double-booked in a day, and on a court/time-slot double-booking | Interview |
| S23 | Scheduler is the **single source of truth for all timing**. No parallel clocks, ever | Session 4 |
| S24 | Admin day-to-day v1 must-haves: mid-season roster edits, rescheduling, **correcting stats after the fact** | Interview |
| S25 | **Corrections are simple overwrites — no audit/change-log trail required on the website.** The AI Board's logging discipline applies to Board operations, not the product | Interview |
| S26 | Admin dashboard v1: upcoming games front and centre, plus a flag for **played games missing scores/stats**. Errors surface visibly — nothing fails silently. Keep lean | Round 3 |

### Build governance (standing rules)

| # | Decision | Source |
|---|---|---|
| S27 | **One task = one branch = one PR.** No agent works on main. **No direct push to production, ever** | Session 7 |
| S28 | Three environments: **Local → Staging → Production**, with separate credentials. Production needs an explicit release gate | Session 7 |
| S29 | **CI is a mandatory verification gate** and folds the GitHub migration into this rebuild | Session 7 |
| S30 | Verification hierarchy: **unit → integration → Playwright/E2E → release validation.** Playwright is the hard pass/fail gate for user-facing behaviour | Session 8 |
| S31 | **Rework limit: three** meaningful failed fix/verify cycles on one piece, then stop and escalate with root-cause hypothesis and evidence | Session 8 |
| S32 | **Build isolation**: each piece built and tested standalone before wiring, then a separate integration pass | Session 5 |
| S33 | **Attempted ≠ verified.** "Done" only with evidence. Named dealbreaker | Interview |
| S34 | Claude Code has final say on **purely technical** decisions already constrained by spec/architecture/security. Escalate when product behaviour, scope, architecture, security, data integrity, cost or lock-in are affected | Session 8 |
| S35 | Zero credentials in source, commits, client code or logs; staging and production secrets fully separated | Session 8 |
| S36 | Communication cadence: **only when flagged or blocked** | Session 6 |
| S37 | Build **incrementally, piece by piece** — Synclaire's leaning, explicitly open to a research-informed different order | Session 4 |

### Eligibility — S38, settled by the league 2026-09-09

**GBL v1 allows minors to register and play.**

| Value | Setting |
|---|---|
| Minors may register | **Yes.** A registration is **not** rejected solely because the applicant is under 18 |
| `guardian_required_under` | **18** — under-18 applicants require a parent or legal guardian signature |
| Signature record | The system records **who signed and their capacity** (`self` / `guardian`) |
| Adults | Sign for themselves |
| `age_as_of_date` | A **fixed season-level date**, set per season. **Never computed from "today"** |
| `minimum_age` | **`null`** — no floor beyond guardian consent. *See note.* |

**This reverses an earlier engineering recommendation** to make v1 18+ only, with
minors and guardian workflow out of scope. That recommendation is **withdrawn by
the league**. The guardian/minor architecture already in `12_registration.md` is
therefore correct as written and should not be removed.

**Note on `minimum_age`.** The league settled the guardian rule and did not state
an age floor, so it is encoded as `null` — which is the faithful reading of
"not rejected solely because the player is underage." This is the one eligibility
value set by engineering rather than the league. **Cost to change:** config edit.

**Why `age_as_of_date` cannot be defaulted or computed.** "18 years old" is
meaningless without a reference date. Computing against the current date makes a
player's eligibility change silently mid-season, on their birthday. The date is
required at season activation and activation fails without it
(`13_configuration.md` §6).

**Consequence — the system stores minors' personal data**, including dates of
birth and guardian details. `16_security.md` §7 applies to it without exception:
admin-only, never in a public or AI-surface response, never in a log line, an
error payload, or a URL.

### Architecture decisions ratified during specification authoring

| # | Decision | Source |
|---|---|---|
| **ADR-010** | **Score Authority — ACCEPTED.** Where authoritative player stat lines exist for a game, the official result score is **derived** from them. `player_game_stat_line` stays authoritative for player statistics; `GameResultService` stays the single canonical mutation authority for official result state; direct score entry is permitted **only where the state model allows it**; a caller cannot create a competing authoritative score by typing over a stat-derived result; `result_source` is **explicit provenance, not a second authority** | Ratified 2026-09-09, on repository evidence verified the same day |

**Acceptance condition satisfied.** ADR-010 was accepted subject to verifying the
cited implementation in the repository. Verified: migration
`0029_games_soft_delete_and_score_source.sql` defines `games.score_source` with a
CHECK constraint; the importer guard at `scripts/import-recleague.cjs:409-420`
skips games marked `live` and logs both values on disagreement; write paths in
`src/index.tsx` (3082, 3692, 3879, 3882) default to `'live'` so an undeclared
caller fails safe.

**One citation withdrawn.** An earlier draft cited a "99-point stat line" test.
That figure is not reproducible from the current database and has been removed
from the specification. The verifiable evidence is the code and schema above, plus
game 1971 — `score_source='live'`, five stat lines totalling 45–36, game still
reading `scheduled 0-0`. It changes nothing about ADR-010, and the withdrawal is
recorded because an unreproducible number in a specification is exactly the
failure mode S33 names.

**Wording note.** ADR-010 is deliberately stated **by state**, not as "stats beat
direct entry." A universal precedence slogan would pre-decide cases the model has
not defined — games with no box score, forfeits, legacy imports, incomplete stat
capture, correction workflows. Authority is established by the explicit
`result_source` state so each of those is decided by its own designated source.

### Deferred (explicitly out of scope for this build)

| # | Item |
|---|---|
| D1 | Legacy data migration / historical import — desired if feasible, **not a hard requirement** |
| D2 | Reckly cutover. Reckly runs the live season **in parallel**, **no data sync between systems** |
| D3 | Current-season operational state. **Build must not entangle with live data** — frozen historical data only, as a test fixture. Explicit lesson from a prior failure |
| D4 | Offline sync / CRDT |
| D5 | Companion mobile app |
| D6 | Captain permissions |
| D7 | Multi-tenancy / other leagues |
| D8 | Officials / referees entity |
| D9 | In-app payments / Stripe |
| D10 | Future multi-admin staff logins (1–2 year horizon; API must not preclude) |

---

## Part 2 — DEFAULTED (nothing here blocks the build)

**Changed 2026-09-09. This section used to say "open — stop and escalate." That
was wrong in practice.** The league owner is not an engineer and can only choose
between options someone else describes; handing back a bare question produces
either a stall or a decision made on no information. Both are worse than a
stated default.

**The new rule:**

> **Every item below has a specified value that gets built. The builder
> implements the stated value. The builder never invents a different one.**

That preserves the property that mattered — no undocumented engineering defaults
— while removing the blocking. Each item records who decided it, so a value that
was mine can be overridden by the league at any time.

| Class | Meaning | Who set it |
|---|---|---|
| **DECIDED** | Purely technical, inside my authority under S34 | Claude Code |
| **DEFAULT** | League policy. A concrete value is set so the build proceeds. **Change it whenever you like** | Claude Code, pending league review |
| **OPEN-FACT** | Not a decision — a fact nobody has looked up yet. Does not block | — |

**"Default" does not mean a silent code fallback.** The value is written into
season config explicitly, and the system still **fails loudly** if the key is
absent (`13_configuration.md` §6). The specification now tells you which value to
write; it does not let code guess.

**Cost of changing one later** is stated per item. Most are a config edit.

---

### G2 — Technical rules constitution — DECIDED
The architecture principles in `01_principles.md` apply as **new-build law**.
Every one traces to an incident in `22_traceability.md`; none is inherited
convention.
**Cost to change:** low before Stage 2, high after — they shape the schema.

### G3 — Build-piece inventory — DECIDED
The inventory is the stage list in `21_implementation-order.md`, decomposed into
**T1–T31** in `24_build-tasks.md` — Stage 0 through full-season acceptance, all
of it, before the build starts. The earlier "12-piece candidate" list is
retired.
**Cost to change:** low — resequencing tasks is cheap; the dependency order is
not arbitrary and should be preserved.

### G4 — Notifications — DEFAULT: not built in v1
Round 2 placed notifications in scope; Round 3 stated no provider is built in and
communications are handled externally. **The later statement wins.** No
notification subsystem is built. `bulkReschedule` emits a complete, structured
change set — every affected game, both times, both venues, affected teams — which
can be read on screen, exported, or fed to a provider later.
**Cost to change:** low. The payload already exists; adding a delivery consumer
does not touch the scheduler.

### O1 — Composite statistic definitions — DEFAULT
**Value set:** ship the metrics that are computable and transparent now — PPG,
RPG, APG, SPG, BPG, plus-minus, and shooting percentages wherever attempts are
tracked. **PIR/EFF uses the standard formula:**

```
PIR = (points + rebounds + assists + steals + blocks)
    − (missed field goals + missed free throws + turnovers)
```

Misses require attempts. Where attempts are not tracked, **PIR is `NULL` and is
shown as "not tracked"** — never approximated. An award computed from a silently
substituted formula is worse than no award, and S9's whole point is that a player
can redo the arithmetic themselves.
**Cost to change:** trivial — it is a config-declared formula, and metrics are
projections, so changing it re-renders without touching stored data.

### O2 — Forfeit semantics — DEFAULT
**Value set:**

```
counts_as: 'win_loss'        awarded_score: [20, 0]
player_stats: 'none'         affects_tiebreak: true
```

Rationale: a forfeit is a real outcome with a real winner, so it counts. `20-0` is
the common rec-league convention and keeps point differential — the S20 default
tiebreak — from being distorted by a game nobody played. No player accrues
statistics for a game that did not happen.
**Cost to change:** config edit, plus a standings recompute. Standings are a
projection, so nothing is stranded.

### O3 — Multi-team tie resolution — DEFAULT
**Value set:** build a **sub-table among the tied teams only**, apply the chain
within it, break out the top team, then **restart the chain** for the remainder.
Where the tied teams have not all played each other, `head_to_head` is skipped for
that group rather than applied on partial data.
Rationale: this is the most common convention in league play and the easiest to
explain to a team that lost a tiebreak.
**Cost to change:** config edit. All four candidate rules are implemented as
strategies.

### O4 — Playoff seed durability — DEFAULT
**Value set:** `durable`. Once seeds are finalised they stand. Each carries a
`basis_snapshot` of the standings it came from, so a later correction produces a
**visible flagged discrepancy** rather than a silent reseed or a silent
contradiction.
Rationale: teams are told their seed and plan around it. Moving it after the fact
costs more trust than the accuracy gains.
**Cost to change:** config edit; the snapshot needed for every alternative is
already written.

### O5 / POLICY-013 — Stat-to-score discrepancy handling — DEFAULT
**Narrowed by ADR-010** — this no longer asks whether scores derive from stats.
The remaining question is what happens when authoritative stat lines disagree with
an independently recorded score.

**Value set:**

```
require_box_score_sum: false      tolerance_points: null
on_mismatch: 'warn'               override_requires: 'reason'
```

Rationale: `block` would make **13 real games unfinalisable** — the league's own
history rejected by its own system. `allow` moves standings with nobody told.
`warn` records both values, surfaces the discrepancy, and lets an authorized
person finalise with a stated reason.

**Already required regardless** (`08_game-results.md` §4): discrepancy detected
automatically; both values recorded; never two competing official scores; every
override carries provenance and a correction path.
**Cost to change:** config edit; discrepancies are recorded from day one, so a
stricter rule can be applied retroactively.

### O6 — Roster eligibility — DEFAULT
**Value set:**

```
roster_lock_date: null       multi_team_allowed: false
fill_ins_allowed: true       max_players_per_team: null
```

Rationale: fill-ins already happen — two legacy players appear in another team's
box score (FACT) — so the system records them rather than pretending otherwise.
The stat line carries its own `team_id`, so a fill-in's points go to the team they
actually played for. No lock date until the league wants one.
**Cost to change:** config edit. `multi_team_allowed` is the one worth a real
look before playoffs.

### O7 — Hosting / infrastructure — DECIDED
**Cloudflare Workers + D1 + Pages**, with **Durable Objects + WebSockets** for the
live tracker. Survived bounded scrutiny; the real constraints — 10GB cap,
single-writer concurrency, transient errors needing retry — are not binding at
GBL's scale, and Cloudflare names live sports scores as the canonical Durable
Objects use case.
**Cost to change:** high after Stage 1. Only the DDL dialect and the real-time
transport actually depend on it.

### O8 — Scheduling objective priority — DEFAULT
**Value set:** satisfy the two hard constraints (S22) and apply **no further
optimisation**, but **report the resulting balance metrics** — home/away split,
rest days, venue and time-slot distribution — so a human can judge the schedule
and re-run.
Rationale: silently optimising for an unchosen objective hides the choice. Showing
the numbers lets the league discover what it actually cares about.
**Cost to change:** low — it is an ordered list of objective keys.

### O9 — Timezone and date-boundary semantics — DECIDED
Store instants in **UTC**; store the league's **IANA timezone on the season**;
derive every display date. The per-day rule ("no team plays twice in a day") uses
the **league-local day**, not UTC — a 9pm game is not tomorrow's game. Never store
a formatted date string as data; legacy did, and every game rendered as "Invalid
Date."
**Cost to change:** high. This is a representation decision baked into the schema.

### O10 — "Reckly" vs "recleague.net" — OPEN-FACT
Alignment documents name the platform **Reckly**; the legacy importer targets
**recleague.net**. They may be one product or two. **This blocks nothing** — the
source is a parameterised external system with a namespaced `external_ref`, which
is correct either way. It only needs answering if and when Phase 2 migration
starts.

### O11 — Waiver / e-signature vendor — DEFAULT, with a real constraint
**Value set:** build the artefact slot; **do not build a custom signature flow.**
Registration captures everything else and stores `document_version`, `signed_at`,
`signer_name`, `signer_capacity`.

**The constraint that is not mine to wave off:** S10 requires a *legally binding*
waiver. Until a vendor fills that slot, **registration should not be the league's
only record of consent** — keep whatever paper or existing process is in use. A
hand-rolled e-signature carries legal risk the league has not accepted and this
specification will not create.
**Cost to change:** low technically — the slot holds a vendor reference.

### O12 — Configuration change retroactivity — DECIDED
**Retroactive.** A config change re-ranks the season under the new chain. One
published set of rules per season is far easier to explain than two eras of
ranking. Every standings computation stamps its config version either way, so the
history stays explicable.
**Cost to change:** low — both behaviours read the same stamp.
---

## Tension worth naming

**S25 (no audit trail) versus the architecture constitution's provenance
instincts.** The product decision is explicit: corrections are simple overwrites
and no change-log is required on the website.

That is a legitimate product call and the specification will follow it. **But it
interacts with S3 + S4:** an anonymous, unauthenticated courtside tracker is a
write surface with no actor identity. With no audit trail either, a wrong stat
has no recoverable history and no attribution.

**RECOMMENDATION — not a requirement:** keep S25 for user-facing behaviour (no
change-log UI, no approval workflow), but retain a minimal internal write log for
the tracker surface specifically — timestamp, device/session token, previous
value. Not because the product asked for it, but because an anonymous write path
without one cannot be debugged when a scorekeeper reports a wrong number.

**DEFAULT set: keep the minimal tracker write log.** The reason is operational,
not philosophical — an anonymous write surface with no history cannot be debugged
when a scorekeeper reports a wrong number, and "a number is wrong and nobody can
tell how it got there" is a support problem the league will actually have.

It stays invisible to users, so S25 is honoured as written: no change-log UI, no
approval workflow, corrections remain simple overwrites.
**Cost to change:** trivial — stop writing the log. Nothing reads it but a
debugger.
