# GBL Backend — Build Specification

**This is the build specification. There is one, and this is it.**

A competent engineer should be able to build the system from these documents
without reading the legacy code and without inventing league rules.

**Status: AUTHORED.** All sections are written. Sections blocked on league policy
carry **typed UNKNOWN slots** — the shape is specified and only the value is
missing. See §Status below.

---

## One specification governs

**REQUIREMENT.** A builder receives **one** specification. Where two documents
describe the same system, one of them is stale and nobody knows which — which is
the exact failure this architecture exists to prevent, applied to its own
documentation.

**If another document covers the same ground**, its unique content is folded in
here and that document is retired. It is not handed to a builder alongside this.

**Worked example.** During review, score-vs-stat authority was held open in one
place and settled in another. It was resolved on 2026-09-09 by ratifying
**ADR-010** (`20_decisions.md`) against repository evidence verified the same day
— not by picking the more convenient reading. That is the procedure below,
applied once already.

### Conflict rule

If any other document disagrees with this one about the backend:

1. **Stop.** Do not pick the more convenient reading.
2. Check whether the claim is evidence-backed here — every rule cites its
   originating incident, and `22_traceability.md` indexes them.
3. Escalate to the Board. Resolve it in **one** document.

---

## Reading evidence citations

Every FACT in this specification is backed by something observable. Most were
observed in the **legacy system**, which lives in a **separate repository**
(`GBL-DOT-COM`) and is still live and serving the league.

**File paths in evidence citations — `src/index.tsx:3082`,
`scripts/import-recleague.cjs:409-420`, `migrations/0029_*.sql`, table and row
counts — refer to that legacy repository.** They are the proof behind a rule, not
files in this one. Do not go looking for them here, and do not port them.

Paths in requirements and tasks refer to **this** repository.

---

## Where the boundaries are

| Layer | Home | Authority |
|---|---|---|
| Policy decisions, R&D records, governance | Notion | Authoritative for **decisions** |
| Build specification (this) | `docs/spec/` | Authoritative for **architecture** |
| Implementation | `src/`, `migrations/` | Must conform to this specification |

This specification cites decisions **by ID** and never restates their value.
Restating one would create a second home for a fact.

---

## How to read this

Read in this order. Each document depends on the ones above it.

### Foundations

| # | Document | What it settles |
|---|---|---|
| 01 | `01_principles.md` | The constitutional rules, as testable engineering requirements |
| 02 | `02_domain-model.md` | Entities, identity, relationships |
| 03 | `03_source-of-truth.md` | Who owns each fact, what is derived, how it is rebuilt |
| 04 | `04_state-machines.md` | Legal states and transitions |
| 05 | `05_database.md` | The schema contract: tables, constraints, indexes |
| 06 | `06_mutations.md` | Every write, with transaction, cascade and failure behaviour |

### Engines

| # | Document | What it settles |
|---|---|---|
| 07 | `07_statistics.md` | Stat lines, derivation, leaderboards, **the live tracker** |
| 08 | `08_game-results.md` | Scores, provenance, finalisation, correction |
| 09 | `09_standings.md` | Records, tiebreaks, determinism |
| 10 | `10_scheduling.md` | Generation, constraints, bulk rescheduling |
| 11 | `11_playoffs.md` | Seeding, brackets, structural progression |
| 12 | `12_registration.md` | Submission, waivers, age verification, PII |
| 13 | `13_configuration.md` | The full config surface and every typed UNKNOWN slot |
| 14 | `14_import-migration.md` | Identity, idempotency, reconciliation (Phase 2) |

### Surfaces and delivery

| # | Document | What it settles |
|---|---|---|
| 15 | `15_api.md` | Endpoint contracts and the four surfaces |
| 16 | `16_security.md` | Actors, the anonymous tracker token, secrets, PII |
| 17 | `17_operations.md` | Environments, gates, backups, rollback |
| 18 | `18_testing.md` | Invariants, adversarial suite, fault injection |
| 19 | `19_acceptance.md` | Definition of done; the full-season acceptance scenario |

### Governance

| # | Document | What it settles |
|---|---|---|
| 20 | `20_decisions.md` | Settled decisions (S-numbers), ratified ADRs, and **open decisions GBL must make** |
| 21 | `21_implementation-order.md` | Build sequence, and which decision is needed when |
| 22 | `22_traceability.md` | Evidence → failure → rule → test, for every rule |
| 23 | `23_verification-handoff.md` | For the independent verifier: what to attack, and how to report |
| 24 | `24_build-tasks.md` | **The builder's queue** — PR-sized tasks, in order, each with its own definition of done |

**If you read only two:** `20_decisions.md` tells you what is not yours to
decide. `22_traceability.md` tells you why every rule exists.

---

## Role boundaries

| Role | Held by | Owns | Reads |
|---|---|---|---|
| **Board / GBL** | Synclaire | Every open decision in `20_decisions.md` | Anything |
| **Builder** | Codex | Implementation conforming to this specification | All of it; enters via the repo's `AGENTS.md`, then `21_implementation-order.md` |
| **Independent verifier** | *not the builder* | Adversarial verification | `23_verification-handoff.md`, then the acceptance tests |

**REQUIREMENT — the verifier is never the author.** A piece is verified by a
session with no context from the one that built it. An agent reviewing its own
work re-runs its own assumptions and finds its own blind spots absent.

**REQUIREMENT.** A builder does not resolve an open decision to unblock itself,
and a verifier does not accept a piece where one was resolved. That check is
`23_verification-handoff.md` §4, and it is the single most likely rule to be
violated under deadline.

---

## First actions for a builder

1. Read `20_decisions.md` Part 2 — the value for every policy item. Build what it
   says; do not substitute your own.
2. Read `21_implementation-order.md` §4 — know which decisions your stage needs.
3. **Inspect the actual repository, database, migrations, runtime, auth, CI and
   test harness.** This specification deliberately does not fabricate the current
   schema; it specifies the target. Produce an implementation delta before
   writing code.
4. Work `24_build-tasks.md` in order — one task, one branch, one PR. Stage 0
   (the rails) comes before any domain code, and its exit criterion is that
   **every gate has refused something.**

---

## Evidence classification

Every material statement in this specification is tagged. **The tags are not
decoration — they say how much weight a claim can bear.**

- **FACT** — observed directly in the repository, schema, or running system. A
  file and line, a query result, or an HTTP response backs it.
- **INFERENCE** — follows from evidence but was not observed directly.
- **REQUIREMENT** — the new system must do this. Established, not proposed.
- **RECOMMENDATION** — a proposed design choice. **Not binding.** A builder may
  raise a better option.
- **UNKNOWN** — appears throughout the engine documents as a typed slot. **It
  does not mean "blocked."** Every one has a value set in `20_decisions.md`
  Part 2, marked **DECIDED** (technical, mine under S34) or **DEFAULT** (league
  policy, set so the build proceeds and changeable at a stated cost). The slot
  stays typed so the value is visible and reversible rather than buried in code.
  **A builder implements the stated value and never substitutes its own.**

An INFERENCE or RECOMMENDATION becomes a REQUIREMENT only by an explicit,
recorded decision. That promotion is itself a change to this specification.

---

## Where things live

| Layer | Home | Authority |
|---|---|---|
| Policy decisions, R&D records, governance, handoffs | Notion | Notion is authoritative for **decisions** |
| Technical specification (this) | `docs/spec/` | Authoritative for **architecture** |
| Implementation | `src/`, `migrations/` | Must conform to this specification |

This specification references decisions **by ID** — `S*` settled, `O*` open,
`G*` gate, catalogued in `20_decisions.md` — and never
restates their value. If you want to know what the tiebreak chain is, the
register in Notion is the only correct source. Restating it here would create a
second home for one fact, which is the failure this whole architecture exists to
prevent.

---

## Ground rules for the builder

1. **Implement the stated value. Never invent a different one.** Every item in
   `20_decisions.md` Part 2 has a specified value — DECIDED (technical) or
   DEFAULT (league policy, set so the build proceeds). Nothing blocks. If you
   find a case with **no** stated value, that is a gap in the specification:
   raise it, do not fill it.
2. **Do not treat legacy behaviour as a requirement.** The legacy system is
   evidence. Every legacy behaviour referenced here carries an explicit verdict:
   PRESERVE, ADAPT, BUILD FRESH, REPLACE, or RETIRE.
3. **Do not add a second way to write a fact.** One canonical mutation authority
   per fact. A convenience route that skips the domain service is a defect even
   if it works.
4. **A UI control is not evidence that an operation exists.** In the legacy
   system, a delete button existed with no handler behind it for months.
5. **Successful execution is not proof.** Assert the resulting state.

---

## Status

**Baseline this specification was written against** — legacy database, verified
2026-09-09: 26 tables, 25 migrations applied, 71 games, 264 players, 809 stat
lines, 14 playoff games, Season 3 active and unresolved.

| Section | Status |
|---|---|
| 01–06 Foundations | AUTHORED |
| 07–14 Engines | AUTHORED (policy-dependent behaviour carries typed UNKNOWN slots) |
| 15–19 Surfaces and delivery | AUTHORED |
| 20 Decisions | AUTHORED — ADR-010 ratified; **every item has a value. Nothing blocks the build** |
| 21 Implementation order | AUTHORED — **RECOMMENDATION pending G3** |
| 22 Traceability | AUTHORED |
| 23 Verification handoff | AUTHORED |

**Sections blocked on policy are authored structurally.** The standings engine
exists with its tiebreak chain as a declared, typed, empty slot. The shape is
specified; only the value is missing. A decision drops in without redesign, and
`13_configuration.md` §5 gathers every slot in one place.

### Scope reset (settled)

Legacy data migration, Season 3 resolution, and RecLeague/Reckly integration are
**Phase 2 — not prerequisites** for this rebuild. Live courtside stat tracking,
registration, scheduling, standings and playoffs are core.

### The cheapest unblocks

**G3** (ratify the build-piece inventory) and **G2** (ratify the technical rules
constitution). Both cost a decision rather than a discovery, and
`21_implementation-order.md` §4 keys everything downstream off them.
