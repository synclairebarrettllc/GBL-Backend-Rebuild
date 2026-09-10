# 14 — Import and Migration

**Direction: ADAPT.** The incremental importer built for the legacy system is the
one piece of that codebase that was engineered rather than accreted. Its rules
are preserved; its implementation is not.

**Scope status (D1 — DEFERRED).** Migrating Season 3 and legacy history is
**Phase 2**, and is not a prerequisite for the rebuild. This document specifies
the shape so it exists when needed, and so the schema does not have to change
later to accommodate it.

---

## 1. Identity is external, never derived

**REQUIREMENT.** Every imported entity carries a stable `external_ref` from its
source system. Matching is by `external_ref` and nothing else.

**Evidence (FACT).** Name-based matching in the legacy importer produced two
records for one human — 4 and 5 stat lines across that person's 4 games — and
invented a third player on another team. A count-based tiebreak was tried and
also failed, because source totals include the games being imported. The fix was
`players.external_ref` plus subset-matching on actual line values.

**REQUIREMENT.** `external_ref` is assigned **once** and namespaced by source
system. Reassigning one silently re-points history (`06_mutations.md` §4.1).

### Adopting pre-existing records

When importing into a database that already holds records without refs, adoption
is by **matching on actual values** — the specific stat lines present — never on
counts and never on names. An ambiguous match is **not resolved automatically**:
it is reported for operator confirmation (B4).

---

## 2. Idempotency

**REQUIREMENT.** Re-running an import over the same source data produces a
**byte-identical database**. Not "no visible change" — identical.

This was achieved and verified in the legacy system and is the baseline, not the
aspiration.

**REQUIREMENT.** An import is resumable. A failure mid-run leaves a consistent
state, and re-running completes the remainder without duplicating what landed
(`04_state-machines.md`, import job machine).

---

## 3. Import precedence — local authorship is never overwritten

**REQUIREMENT.** An import never overwrites a result or stat line that originated
locally.

```
if the existing result was authored locally (entered, or derived from
   locally captured stat lines):
    leave it alone; record it in the import report, with both values
```

This is distinct from ADR-010's authority rule (`08_game-results.md` §2). ADR-010
says which **store** owns a score; this says which **actor** may act on it. A
locally authored `derived` result is protected here for the second reason, not
the first.

**Evidence (FACT) — verified in the legacy repository (`GBL-DOT-COM`) on
2026-09-09:**

- `scripts/import-recleague.cjs:409-420` — the guard skips any game with
  `score_source = 'live'`, counts it as `protectedLive`, and emits
  `ours X-Y, source says A-B` when the values disagree.
- The comment above it records the deliberate design: the source's official
  score comes from the header and its lines from the tables, with **no
  reconciling** — because 13 games in the source do not sum to their own posted
  score.
- Migration 0029 defines the column; `src/index.tsx` write paths default to
  `'live'`, so an undeclared caller fails safe.

`score_source` was the legacy guard; `result_source` (`08_game-results.md`) is
its specification.

---

## 4. Deletion is a decision, not an absence

**REQUIREMENT.** A record soft-deleted locally (`deleted_at`) is **not**
resurrected because it still exists upstream. Deliberate deletion outranks source
presence.

**Evidence (FACT).** The legacy importer initially treated a `409` response as
success — it read `game_id` off the error body and continued, then failed two
steps later with "Game not found." The corrected behaviour: check the status, and
a `409` carrying `deleted: true` means *respect the deletion*.

**REQUIREMENT.** The import report lists every record skipped for this reason. A
silent skip and a silent overwrite are equally unacceptable.

---

## 5. Dry run

**REQUIREMENT.** Dry run is the **default** for a first invocation
(`06_mutations.md` §5). It reports every create, update, skip and conflict, and
changes nothing.

**REQUIREMENT.** The report distinguishes:

| Class | Meaning |
|---|---|
| create | no local record |
| update | local record differs and is not locally-authored |
| skip — live | local record wins |
| skip — deleted | deliberately deleted locally |
| conflict | ambiguous identity; **operator must resolve** |

---

## 6. Reconciliation — the hard requirement

**REQUIREMENT — standing constraint.** *Historical numbers must reconcile exactly
wherever migration is attempted.*

A migration is not complete when it finishes without error. It is complete when
the numbers match.

**REQUIREMENT.** A migration produces a reconciliation report comparing source
and destination on, at minimum:

- record counts per entity
- per-player stat totals across every tracked category, **keyed on source player
  id** — never on name
- per-team records
- per-game scores
- the set of records deliberately excluded, with reasons

**REQUIREMENT.** Any discrepancy is **explained or the migration is not accepted**.
"Close enough" is not a state this system recognises.

**Evidence (FACT).** This is achievable — stat parity with the source was proven
across 8 categories keyed on source player id. It is also necessary: three
different player counts (217 / 220 / 237) circulated as fact for weeks before
reconciliation showed they measured three different things, and the fourth (217)
was stale and never reproducible.

**REQUIREMENT — count what you say you are counting.** The reconciliation report
states the definition of each number it reports. "220 players" is meaningless;
"220 players with at least one stat line in Season 3" is a fact.

---

## 7. Verified backups gate every migration

**REQUIREMENT.** No migration or bulk import runs without a **verified** backup
taken immediately before it.

Verified means the snapshot passes, and the file is discarded if it does not:

- taken with the SQLite online backup API, **never** a file copy under WAL
- `PRAGMA integrity_check` returns `ok`
- `PRAGMA foreign_key_check` returns nothing
- per-table row counts match the source
- content checksums match
- a non-empty floor — a snapshot of nothing is not a valid backup
- WAL folded so the file is **self-contained**

**Evidence (FACT).** Every one of these criteria exists because the first version
of the backup script reported success on a garbage snapshot: the row-count loop
skipped every check on a table-less database, and the content check compared two
empty strings and called it a match. It was caught only by deliberately feeding
it a corrupt database. **A verifier that has never been shown a bad input is
untested.**

**REQUIREMENT.** Backup verification is itself tested with a known-bad database
in CI.

---

## 8. Source system — POLICY — O10

Alignment documents name the current platform **Reckly**. The legacy importer
targets **recleague.net**.

**REQUIREMENT.** Do not conflate them. Until confirmed, the specification treats
the source as a parameterised external system with a namespaced `external_ref`,
which works correctly whether they are one system or two.

---

## 9. Migration sequencing (Phase 2)

When D1 is undeferred:

1. Verified backup of the legacy database
2. Import into a **staging** environment — never production first
3. Reconciliation report; every discrepancy explained
4. Operator review and explicit acceptance
5. Production import behind the release gate (S28)
6. Post-migration reconciliation re-run **against production**

**REQUIREMENT.** Step 6 is not optional. A reconciliation that passed in staging
proves the transform, not the production run.

---

## 10. Acceptance tests

| Test | Asserts |
|---|---|
| `import.replay-noop` | Re-running over identical source yields a byte-identical database |
| `import.identity-by-ref` | Identical names with different refs stay separate records |
| `import.no-name-matching` | No code path matches entities by name |
| `import.ambiguity-escalates` | An ambiguous match is reported, never auto-resolved |
| `import.precedence` | A locally authored result survives an import that disagrees |
| `import.discrepancy-records-both` | A disagreement is reported with both values, never reconciled |
| `import.respects-deletion` | A soft-deleted record is not resurrected |
| `import.dry-run-default` | A first invocation writes nothing |
| `import.report-classifies` | Every record appears in exactly one report class |
| `import.resumable` | An interrupted import completes on re-run without duplication |
| `import.409-not-success` | A non-2xx response is never treated as success |
| `migration.reconciles-exactly` | Source and destination totals match on every category |
| `migration.definitions-stated` | Every reported count carries its definition |
| `backup.rejects-corrupt` | A known-bad database is refused and no file is kept |
| `backup.self-contained` | A verified snapshot has no `-wal`/`-shm` dependency |

**`backup.rejects-corrupt` is the load-bearing test in this document.** Every
other guarantee here assumes a recoverable starting point.
