# 22 — Traceability Matrix

Every architectural rule in this specification traces to an observed failure and
forward to a test that locks it out.

**The purpose.** A rule whose origin nobody remembers becomes a rule someone
relaxes. This document is what makes "why is it like this?" answerable in two
years by reading, rather than by re-discovering.

**How to read a row:** the evidence was observed in the legacy system (FACT); the
failure is what it caused; the rule is the specification's response; the test is
what proves the response holds.

---

## 1. Source-of-truth failures

| Evidence (FACT) | Failure | Rule | Where | Test |
|---|---|---|---|---|
| `seasons.status` **and** `seasons.is_active`, queried at 16 vs 5 sites | Two seasons active at once | One fact, one home; single-active enforced by **partial unique index** | `03`, `05` | `season.single-active` |
| `teams.wins`/`losses` as both accumulator and truth; two drift paths confirmed live | Records permanently wrong after any reversal | Standings are a **pure projection**; no stored record | `09` | `standings.correction-reverses`, `standings.no-stored-record` |
| `players.season_*` (8 cols) + `games_played` written on every save, read by nothing; **3 players already disagreed with their own stat lines** | Silent drift in an unread cache | No stored season totals | `07` | `stats.no-stored-totals`, `totals.recompute-equality` |
| Three routes writing `game.home_score` with **0, 4 and 4** validation checks | Rules depended on which URL was used | `game` has **no score column**; `GameResultService` is sole authority | `08` | `result.no-score-on-game`, `result.single-authority` |

---

## 2. State and status failures

| Evidence (FACT) | Failure | Rule | Where | Test |
|---|---|---|---|---|
| `playoff_games.status` had **no CHECK**; wrote `'completed'` while ~45 sites compared `'final'` | Every comparison permanently false, silently, for months | Canonical status vocabulary; **`CHECK` on every status column** | `04` | `status-checks-present` |
| `games.status` **had** a CHECK — the same bad write failed **loudly** the same day | — | The schema's ability to say no is the control | `04`, `05` | (same) |
| Bracket progression inferred from **round-name text**; correct fix touched 24 sites | Structure depended on a display string | Progression is a **foreign key** (`winner_advances_to_match_id`) | `11` | `bracket.structural-progression`, `no-round-name-logic` |
| `playoff_games` as a table parallel to `games` | Two homes for one game's status and timing | Playoff games **are** `game` rows; scheduler owns all timing (S23) | `10`, `11` | `bracket.no-parallel-table`, `schedule.no-parallel-clock` |
| `reopen` route set `in_progress`, cleared the lock, defined no propagation | Corrections with undefined downstream effects | Correction is a **first-class named operation** with an enumerated cascade | `08` | `result.correction-cascade`, `result.correction-bounded` |

---

## 3. Statistics failures

| Evidence (FACT) | Failure | Rule | Where | Test |
|---|---|---|---|---|
| FGM collected as a combined field; "3 twos + 2 threes" entered as FGM=3, 3PM=2 | **8 points instead of 12** | Store **2PM/3PM** separately; points derived | `07` | `stats.scoring-arithmetic` |
| Validation required FGA and rejected `fgm > fga`; GBL records makes, so FGA arrived as `0` | **Every real stat line rejected** — `player_game_stats` empty for the app's life | Attempts nullable; `NULL` ≠ `0` | `07` | `stats.makes-only-line-accepted`, `stats.attempts-null-vs-zero` |
| Game 1971: five real stat lines entered by the owner, still reading `scheduled 0-0` | Saving a box score recomputed nothing | Stat write → score derivation, **same transaction** | `03`, `07`, `08` | `stats.derivation-edge` |
| `/players` returned all 264 unpaginated, including **31 with zero games** ("Kobe (DNP)") | Leaderboards ranked non-players | Zero-game exclusion; mandatory pagination | `07`, `15` | `stats.leaderboard-excludes-zero-games`, `api.pagination-enforced` |
| Two Clippers players appeared in a Kings box score, unrepresented | Fill-ins had no model | Stat line carries its own `team_id`; attribution by line, not roster | `07`, `08` | `stats.fill-in-attribution` |
| Stat sheet held a game in client state and saved once; a re-render lost it | Partial save overwrote a valid line | **Progressive persistence**; every increment is a write | `07` | `tracker.progressive-save` |
| 13 games have box scores that do not sum to their posted score | Real, source-side | Do **not** validate lines against team score; O5 typed slot | `07`, `08` | `result.mismatch-recorded` |

---

## 4. Identity and import failures

| Evidence (FACT) | Failure | Rule | Where | Test |
|---|---|---|---|---|
| Name-based re-derivation made one person **two players** (4 and 5 lines across 4 games) and invented a third | Duplicate humans, corrupted totals | Identity by **`external_ref`**; never by name | `14` | `import.identity-by-ref`, `import.no-name-matching` |
| A **count-based** tiebreak also failed — source totals include the games being imported | A plausible fix that was wrong | Adoption by **matching actual line values**; ambiguity escalates | `14` | `import.ambiguity-escalates` |
| Importer read `game_id` off a **409** and continued; failed later with "Game not found" | An error body treated as success | Check status before body; `409` is never partial success | `14`, `15` | `import.409-not-success`, `api.status-codes-truthful` |
| `score_source` guard (`import-recleague.cjs:409-420`) skips `live` games and logs both values; write paths default to `'live'` | (The control working) | **ADR-010**: authority by `result_source` state. **Import precedence**: local authorship never overwritten | `06`, `08`, `14` | `adr010.derived-overwrite-refused`, `import.precedence` |
| Game 1971: `score_source='live'`, five stat lines totalling 45–36, game reads `scheduled 0-0` | The guard held; the derivation edge was never built | Stat write → score derivation, same transaction | `07`, `08` | `stats.derivation-edge`, `adr010.stat-lines-produce-score` |
| Soft-deleted records still present upstream | Deletion vs absence indistinguishable | `deleted_at` outranks source presence | `14` | `import.respects-deletion` |
| Three player counts (217/220/237) circulated as fact; 217 stale and unreproducible | Numbers without definitions | Every reported count carries its **definition** | `14` | `migration.definitions-stated` |

---

## 5. Read-path and API failures

| Evidence (FACT) | Failure | Rule | Where | Test |
|---|---|---|---|---|
| `deleted_at` required auditing **62 read sites**; 45 filtered, 17 not, only 4 deliberate — **11 genuine gaps, 7 user-visible** | A rule enforced by memory at 62 sites | Filter in the **data access layer**, by construction; opt-in to include deleted | `15` | `api.deleted-filtered-everywhere` |
| First audit summary said "~40 fixed, 3 deliberately left" against a 60-site scope | A summary that sounded complete concealed 11 gaps | Coverage statements must **reconcile**: filtered + documented exceptions = total | `18`, `19` | (process rule — `19_acceptance.md` §5) |
| A single route file reached **8,373 lines** | Domain logic living in routes | Routes parse, authorise, delegate, serialise — no domain logic | `15` | `api.no-sql-in-routes` |
| Admin delete button with **no handler**, for months | Indistinguishable from success | No silent no-ops; a UI control is not evidence an operation exists | `06` | `mutation.no-silent-noop` |
| Mixed date formats stored | Every game rendered "Invalid Date" | One instant representation; never store formatted strings | `10` | `schedule.date-round-trip` |

---

## 6. Operational failures

| Evidence (FACT) | Failure | Rule | Where | Test |
|---|---|---|---|---|
| `external_ref` reads shipped ahead of migrations 0027/0028 | **Production outage** — admin schedule down | Migrate, then deploy; **migration guard** at `prebuild` | `17` | `ops.migration-guard-blocks` |
| `deleted_at`/`score_source` reads shipped ahead of 0029 | **Production outage** — public leaderboards and standings 500'd **during live stat entry** | Same, plus a health check comparing schema and code expectations | `17` | `ops.health-check-schema-version` |
| Backup script reported success on a **garbage snapshot** — the row-count loop `continue`d past missing tables; content check compared two empty strings | A verifier that passed anything | Every verification criterion in `17` §5; **failure discards the file** | `14`, `17` | `backup.rejects-corrupt` |
| Verification itself created `-wal`/`-shm` sidecars | Snapshots not self-contained | WAL fold, then re-verify | `17` | `backup.self-contained` |
| Deleting an admin orphaned **24 `admin_logs`** rows — `ON DELETE CASCADE` with `foreign_keys` **off by default** | Silent referential damage | Deactivate, never delete; `PRAGMA foreign_keys = ON` asserted **and tested** | `16` | `sec.fk-pragma-on`, `sec.admin-delete-prohibited` |
| CI assumed a `webapp/` subdirectory when the git root **is** the app | Red CI, 6-second failure | CI runs on a clean checkout and matches local gates | `17` | `ops.ci-matches-local` |
| `localhost:3000` resolved via IPv6 to a different project's server | A false "site is down" diagnosis; nearly aimed an import at the wrong process | Explicit host binding; never assume a port belongs to you | `17` | (operational practice) |
| Tracked seed file contains **real player names** | PII in the repository | Repository stays **private**; PII never public, logged, or in URLs | `16` | `sec.no-pii-in-logs` |

---

## 7. Coverage check

**Every rule in this specification traces to a row above, or to a settled
decision (S1–S37) in `20_decisions.md`, or to an open decision it deliberately
declines to make.**

Three categories, exhaustively:

| Category | Meaning |
|---|---|
| **Evidence-driven** | A failure happened. The rule prevents its recurrence. The table above. |
| **Decision-driven** | The league decided (S-numbered). The specification implements it. |
| **Deliberately open** | Nobody has decided. A **typed UNKNOWN slot** exists and stays empty. |

**REQUIREMENT.** A rule that fits none of these three categories is an
engineering preference wearing a requirement's clothes, and should be challenged.

**REQUIREMENT.** When a new failure is found, it is added here **with its
evidence**, and the rule it produces carries a test. The matrix grows by
incident, not by opinion.
