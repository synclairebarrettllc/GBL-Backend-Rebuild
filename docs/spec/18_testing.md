# 18 — Testing Strategy

**The governing standard: "attempted" and "verified" are different states, and
"done" requires evidence.** This is a named dealbreaker for this project, not a
preference.

---

## 1. What counts as evidence

**REQUIREMENT.** A claim that something works is backed by a command and its
output. Not a description of what the code does. Not "the change looks correct."

**REQUIREMENT — assert the resulting state, not the absence of an error.**
Successful execution is not proof.

**Evidence (FACT).** Every significant defect in the legacy system passed this
weaker bar:

| Defect | Why "it ran without error" hid it |
|---|---|
| Delete button with no handler | The click succeeded. Nothing happened. Indistinguishable from success for months |
| `player_game_stats` empty for the app's life | Saves returned success; validation rejected every real line downstream |
| Game 1971 at `scheduled 0-0` | Five stat lines saved successfully. No score was derived |
| Backup script passing a garbage snapshot | The script exited 0. The file was worthless |
| Importer treating a `409` as success | It read a field off an error body and continued |

**REQUIREMENT — a verifier that has never been shown a bad input is untested.**
The backup script's defects were found only by deliberately feeding it a corrupt
database. Every guard in this system ships with a test that proves it **refuses**
something.

---

## 2. Test layers

| Layer | Scope | Speed | What it protects |
|---|---|---|---|
| **Static checks** | whole repo | seconds | structural rules that cannot be enforced at runtime |
| **Invariant tests** | database + services | fast | the architecture's core claims |
| **Unit** | pure functions | fast | derivation arithmetic, tiebreak criteria |
| **Service** | one service + real database | medium | mutation contracts, transactions |
| **Integration** | multiple services | medium | cascades, blast radius |
| **Adversarial** | whole system | medium | the failures that actually happened |
| **Fault injection** | whole system | slow | partial-failure behaviour |
| **End-to-end** | browser + system | slow | the acceptance scenario (`19_acceptance.md`) |

---

## 3. Static checks

These enforce rules that no runtime test can, because they are about **what code
exists**, not what it does.

| Check | Rule |
|---|---|
| `no-sql-in-routes` | No SQL outside the data layer (`06_mutations.md` R5) |
| `no-string-sql` | All SQL parameterised (`16_security.md` §5) |
| `single-score-writer` | Only `GameResultService` writes score columns |
| `no-stored-totals` | No column stores a player's season totals or a team's record |
| `no-score-on-game` | `game` has no score column |
| `no-parallel-playoff-table` | Playoff games are `game` rows |
| `no-date-on-bracket-match` | Matches carry no timing columns |
| `status-checks-present` | Every status column has a `CHECK` constraint |
| `no-secrets` | No credential in tree or history |
| `no-round-name-logic` | No engine reads `round_label` or `round_number` |

**Why static.** Each of these describes a defect that is invisible at runtime
until the exact wrong situation occurs — and by then it is in production. A
grep-level check runs in seconds on every PR.

---

## 4. Invariant tests

The architecture's load-bearing claims, asserted directly.

| Invariant | Test |
|---|---|
| One active season per league | `season.single-active` |
| One stat line per player per game | `stats.grain` |
| Projections equal fresh recomputation | `totals.recompute-equality`, `standings.recompute-equality` |
| Full rebuild from authoritative rows is byte-identical | `reconstruction.full-rebuild` |
| Foreign keys are enforced on every connection | `mutation.fk-enforcement` |
| Every mutation is idempotent under replay | `mutation.idempotent-replay` |
| Every mutation's blast radius is bounded | `mutation.blast-radius` |
| Every illegal transition is rejected | one per state machine |

**REQUIREMENT — `reconstruction.full-rebuild` is non-negotiable.** Delete every
projection, recompute from authoritative rows, diff. If anything fails to
reconstruct, it was secretly authoritative and `03_source-of-truth.md` is wrong.

**REQUIREMENT — test illegal transitions, not just legal ones.** Every legacy
failure lived in a path nobody tested. A state machine tested only on its happy
path is untested.

---

## 5. The adversarial suite

**REQUIREMENT.** Every verified historical failure has a permanent regression
test. These are not hypothetical coverage — each one is a bug that happened.

| Test | The failure it locks out |
|---|---|
| `stats.scoring-arithmetic` | 3 twos + 2 threes = 12, not 8 |
| `stats.makes-only-line-accepted` | Attempts-required validation rejecting every real line |
| `stats.attempts-null-vs-zero` | `0` attempts read as "not tracked" |
| `stats.derivation-edge` | Stat lines saved, no score derived (game 1971) |
| `standings.correction-reverses` | Accumulators that never decrement |
| `result.single-authority` | Three routes, three rule sets, one column |
| `season.single-active` | Two seasons active via a duplicate flag |
| `bracket.structural-progression` | Progression inferred from round names |
| `bracket.correction-bounded` | A correction rewriting the whole bracket |
| `api.deleted-filtered-everywhere` | 17 of 62 read sites missing a filter |
| `import.identity-by-ref` | One human becoming two players |
| `import.409-not-success` | An error body read as a success payload |
| `mutation.no-silent-noop` | A control with no behaviour behind it |
| `backup.rejects-corrupt` | A verifier that passes garbage |
| `ops.migration-guard-blocks` | Code shipped ahead of its migrations |

**REQUIREMENT.** A test may not be deleted because it is "old." It is deleted only
when the *structure* that made the bug possible no longer exists — and the
deletion says which structural change made it unnecessary.

---

## 6. Fault injection

**REQUIREMENT.** Every multi-step mutation is tested with a failure injected at
each step.

**Assertion:** zero partial state. Not "mostly consistent" — the database is
byte-identical to its pre-attempt state (`06_mutations.md` R8).

Covered specifically:

- stat write failing after the line is written but before score derivation
- `assignToTeam` failing at each of its four rows
- bulk reschedule failing partway through
- import interrupted mid-run, then resumed
- correction cascade failing during bracket propagation

**REQUIREMENT.** Connection loss during live tracking is tested as a first-class
case, not an edge case. It is the expected condition in a gym.

---

## 7. Property-based testing

**REQUIREMENT.** The derivation engines are property-tested, because example-based
tests confirm the cases the author thought of — and the legacy failures were all
in cases nobody thought of.

| Property | Engine |
|---|---|
| Recomputing standings twice yields identical output | standings |
| Standings are invariant to game insertion order | standings |
| Tiebreak chains always produce a total ordering | standings |
| Derived score always equals the sum of line points | results |
| Season totals always equal the sum of stat lines | statistics |
| Import replay is a no-op for any source dataset | import |
| Bracket propagation always terminates | playoffs |

---

## 8. End-to-end

**REQUIREMENT.** E2E tests drive the real UI against a real database and assert
**database state**, not just rendered text. A page that displays the right number
from the wrong source is still broken.

**REQUIREMENT.** The live tracker is E2E tested including interruption: enter
stats, kill the tab mid-game, reopen, and assert nothing was lost
(`07_statistics.md` §5).

---

## 9. What is not tested, and why that is stated

**REQUIREMENT.** Deliberate coverage gaps are **documented with a reason**, not
left as silence.

**Evidence (FACT).** The `deleted_at` audit is the case study: the first pass
reported "~40 fixed, 3 deliberately left" against a 60-site scope. The real
numbers were 45 filtered, 17 unfiltered, and only **4** deliberate — meaning 11
genuine gaps were hidden inside a summary that sounded complete. The final state
(57 of 62, with 5 documented exceptions) is defensible precisely because each
exception is named.

**REQUIREMENT.** Any statement of coverage reconciles: filtered + documented
exceptions = total, with the total stated. A number that does not add up is a
finding.

---

## 10. CI enforcement

**REQUIREMENT (S29).** The full suite runs in CI on every PR and blocks merge on
failure.

**REQUIREMENT.** CI runs on a clean checkout with no local database
(`17_operations.md` §3), and includes the meta-tests: migrations apply to a fresh
database, the backup script refuses a bad one, the secret scan passes.

**REQUIREMENT — no skipped tests on `main`.** A skipped test is either deleted
with a reason or fixed. A permanently skipped test is a lie in the report.
