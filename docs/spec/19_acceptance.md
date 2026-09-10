# 19 — Acceptance and Definition of Done

The system is not accepted because it was built. It is accepted because a full
season runs through it and the numbers reconcile.

---

## 1. Definition of done — per piece

A build piece is done when **all** of these hold. Any one missing means
*attempted*, not *done*.

1. Its mutation contracts are implemented exactly as specified in
   `06_mutations.md`.
2. Its acceptance tests pass — the named tests in its own document, not a
   substitute set.
3. Its invariants hold under `18_testing.md` §4.
4. Fault injection at every step leaves zero partial state.
5. Its blast radius is bounded and tested.
6. It introduces no second home for any fact in `03_source-of-truth.md`.
7. Every policy value it consumes **matches `20_decisions.md` Part 2** — not a
   nearby value, not a more convenient one, and not one invented to unblock.
8. Evidence is attached: commands run and their output.

**REQUIREMENT — rule 7 is the one most likely to be violated under deadline.** A
builder who needs a tiebreak chain to finish will invent a reasonable one. That
converts an open league decision into an undocumented engineering default, which
is exactly how the legacy system acquired rules nobody agreed to.

---

## 2. The acceptance scenario: a full season, end to end

**REQUIREMENT.** The system is accepted by running a complete synthetic season.
This is a single automated scenario, not a checklist a human walks through.

### Phase 1 — Setup

1. Create a league, a season in `draft`, two divisions (S13).
2. Attempt to activate with an incomplete config → **rejected**, and the error
   names the missing required keys (`13_configuration.md` §6).
3. Complete the config; activate.
4. Attempt to activate a second season in the league → **rejected by the
   database**, not by application code.

### Phase 2 — Registration

5. Submit registrations, including one on a phone-sized viewport, one
   interrupted mid-flow and resumed, and one submitted twice with the same
   `operation_id`.
6. Assert: **no Person and no Player exist yet**; the double submission produced
   **one** registration.
7. Submit a registration with a name identical to an existing person → the system
   **suggests**, does not link.
8. Accept and assign. Assert Person, Player and RosterMembership were created in
   one transaction.
9. Assert no public endpoint returns any registration field.

### Phase 3 — Scheduling

10. Generate a schedule. Assert **nothing was written**.
11. Commit it. Assert every hard constraint holds.
12. Attempt to schedule a second game on the same court at the same time →
    **rejected by the database**, error naming the conflicting game.
13. Attempt to give a team two games in one **league-local** day → rejected.
14. Bulk-reschedule a venue closure as a dry run → full change set reported,
    nothing written. Commit it → atomic; the change set includes every affected
    game and both time/venue pairs.

### Phase 4 — A game, live

15. Issue a tracker token. Assert it cannot read or write any other game.
16. Enter stats progressively, including **3 two-pointers and 2 three-pointers**.
    Assert the derived score reflects **12 points**, not 8.
17. Enter a line with makes and **no attempts**. Assert it saves, and that its
    percentages serialise as `null`, not `0`.
18. Kill the connection mid-game; reopen. Assert nothing entered was lost.
19. Replay a write with its `operation_id`. Assert nothing changed.
20. Record a **fill-in** — a player on one team's roster appearing for another.
    Assert the points count for the team on the stat line.
21. Assert the derived score updated **in the same transaction** as each stat
    write, and that the game left `scheduled` on the first line.
22. Attempt to finalize with the tracker token → **refused**.
23. Submit. Admin finalizes. Assert standings moved only now, not at `completed`.

### Phase 5 — The rest of the season

24. Play out every game across both divisions, mixing derived results and
    directly entered ones.
25. Attempt `enterResult` on a game that has stat lines → **rejected**.
26. Run an import that disagrees with a locally entered result → the local result
    **survives**, and the skip appears in the report.
27. Soft-delete a game, then re-run the import → the game is **not resurrected**,
    and the skip is reported.
28. Attempt to delete a game that has stat lines → **refused**, with the
    alternative named.

### Phase 6 — Standings and correction

29. Assert standings are computed, carry a `config_version`, and can name the
    criterion separating any adjacent pair.
30. Force a multi-team tie. Assert it resolves by the configured strategy
    (default `sub_table_restart`), and that the output **names the strategy and
    the separating criterion** — never a silent ordering.
31. Snapshot the full standings table.
32. Correct a finalized game from week 3. Assert the cascade ran.
33. **Reverse the correction. Assert the standings table is byte-identical to the
    snapshot.**

### Phase 7 — Playoffs

34. Close the season with games outstanding → **rejected**, and the error **lists
    the games**, not a count.
35. Resolve them; close.
36. Finalize seeds. Assert every seed has a `basis_snapshot` written in the same
    transaction.
37. Generate the bracket. Assert every match and every
    `winner_advances_to_match_id` edge exists **before** the bracket leaves
    `draft`.
38. **Rename every round label in the database. Assert no bracket behaviour
    changes.**
39. Play the bracket. Assert winners propagate one hop along edges.
40. Correct a first-round result **without changing its winner** → assert
    **nothing propagates**.
41. Correct a first-round result **so the winner changes** → assert propagation
    follows the edges, and every match not reachable along them is
    **byte-identical**.

### Phase 8 — Reconstruction and reconciliation

42. Delete every projection. Recompute. Assert **byte-identical** results.
43. Take a verified backup. Assert it is self-contained and passes every check.
44. Feed the backup verifier a known-corrupt database. Assert it **refuses and
    keeps no file**.
45. Restore the backup into a clean environment. Assert the season replays
    identically.

---

## 3. System-level acceptance criteria

Beyond the scenario:

| Criterion | Standard |
|---|---|
| **Reconstruction** | Projections rebuild byte-identically from authoritative rows |
| **Reconciliation** | Where migration is attempted, historical numbers reconcile **exactly**, with every count carrying its definition |
| **No silent failure** | Every rejected operation produces a typed, visible error (S26) |
| **No second home** | Static checks pass; no fact has two authoritative stores |
| **Bounded blast radius** | Every mutation's cascade is enumerated and tested |
| **Decisions honoured** | Every value in `20_decisions.md` Part 2 is implemented as stated, written to config explicitly, failing loudly when absent — never substituted by a builder |
| **Security** | Every test in `16_security.md` §11 passes |
| **Operations** | Every gate in `17_operations.md` has demonstrably refused something |

---

## 4. What "done" explicitly does not mean

| Not done | Why |
|---|---|
| "The code is written" | Untested code is a hypothesis |
| "It ran without errors" | Every major legacy defect ran without errors |
| "The UI shows the right number" | It may be reading the wrong source |
| "Tests pass" — with tests skipped | A skipped test is a lie in the report |
| "It works on my machine" | Both outages worked locally |
| "Close enough on the numbers" | Reconciliation is exact or it is not reconciliation |
| "I picked something sensible for the open question" | That is how undocumented rules are born |

---

## 5. Acceptance is a gate, not a review

**REQUIREMENT.** The scenario in §2 is automated and runs in CI. Acceptance is
reported by the suite, not asserted in a summary.

**Evidence for insisting on this (FACT).** A hand-written audit summary in this
project reported "~40 fixed, 3 deliberately left" against a 60-site scope. The
real state was 45 filtered, 17 unfiltered, 4 deliberate — 11 genuine gaps
concealed inside a sentence that sounded complete, caught only because the
numbers were asked to add up.

**A suite cannot round.**
