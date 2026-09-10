# 23 — Independent Verification Handoff

**Audience: whoever verifies a build piece — and it must not be whoever wrote
it.** Independence is the whole mechanism. An agent reviewing its own work
re-runs its own assumptions.

Your job is **not** to confirm the builder's work. It is to try to break it, and
to report what you find with evidence. A verification pass that finds nothing and
cannot show what it attacked has verified nothing.

**Current role assignment:** Codex builds the backend. Verification is therefore
someone else — a Claude Code session, a human reviewer, or a second Codex session
with no context from the one that wrote the code. **Do not hand a piece back to
its own author to verify.**

---

## 1. The standard you are enforcing

**S33 — attempted ≠ verified. "Done" only with evidence.** This is a named
dealbreaker for this project.

**REQUIREMENT.** Reject any completion claim that rests on:

| Weak claim | Why it fails |
|---|---|
| "It ran without errors" | Every major legacy defect ran without errors |
| "The UI shows the right number" | It may be reading the wrong source |
| "Tests pass" (with tests skipped) | A skipped test is a lie in the report |
| "It works locally" | Both production outages worked locally |
| "Close enough on the numbers" | Reconciliation is exact or it is not reconciliation |

**REQUIREMENT — assert resulting state, not the absence of an error.** Query the
database. Compare to what the specification says should be there.

---

## 2. Where the bodies are buried

These are the places this system has actually broken. Attack them first — they
are not hypothetical, and `22_traceability.md` carries the evidence for each.

### Tier 1 — highest yield

| Target | The attack | Expected behaviour |
|---|---|---|
| **The derivation edge** | Write stat lines, then read the game result | Score updated **in the same transaction**. Legacy did not do this — game 1971 still reads `scheduled 0-0` next to 81 points of real box score |
| **Scoring arithmetic** | Enter 3 two-pointers and 2 three-pointers | **12 points.** Legacy produced 8 |
| **Attempts vs zero** | Save a line with makes and no attempts | Saves. Percentages are `null`, never `0`. Legacy rejected every real line this way |
| **Second home for a fact** | Search the schema for any stored total, record, rank, or score column | None exist. Four separate legacy drift paths came from this |
| **Deleted-row leakage** | Soft-delete a game, then hit **every** read endpoint | Absent everywhere. The legacy audit found 17 of 62 sites unfiltered |
| **Migration/code skew** | Deploy code reading a column before its migration applies | Build refuses. This caused **two production outages**, one during live stat entry |

### Tier 2 — structural

| Target | The attack | Expected behaviour |
|---|---|---|
| **Progression by label** | Rename every bracket round label in the database | **Nothing changes.** Legacy inferred progression from round names |
| **Blast radius** | Correct one finalised game; diff the entire database | Only the enumerated cascade moved. Everything else byte-identical |
| **Idempotency** | Replay every mutation with the same `operation_id` | No duplicates, no state change, original outcome returned |
| **Partial state** | Inject a failure at each step of every multi-step mutation | Zero partial writes. Not "mostly consistent" — byte-identical to pre-attempt |
| **Reconstruction** | Delete every projection; recompute | Byte-identical. If anything fails to rebuild, it was secretly authoritative |
| **Status vocabulary** | Look for a status column without a `CHECK` | None. `playoff_games.status` had none and drifted silently for months |

### Tier 3 — the anonymous write surface

| Target | The attack | Expected behaviour |
|---|---|---|
| **Tracker token scope** | Use a game's token against another game | Refused. The token is the authorization; the game is the scope |
| **Token escalation** | Attempt finalize, roster edit, schedule change, admin read | All refused |
| **Token lifetime** | Use a token after finalisation and after revocation | Refused |
| **Tampering** | Look for any tracker endpoint accepting a `game_id` | None exists — there is nothing to tamper with |
| **PII leakage** | Grep every public and AI-surface response, log line, error payload and URL | No phone, email, DOB, or emergency contact. Ever |

---

## 3. The verifier's checklist

For each build piece, confirm **all eight** or report it as not done
(`19_acceptance.md` §1):

1. Mutation contracts implemented as specified in `06_mutations.md`
2. Named acceptance tests pass — **the named ones**, not substitutes
3. Invariants hold (`18_testing.md` §4)
4. Fault injection at every step leaves zero partial state
5. Blast radius bounded and tested
6. No second home for any fact in `03_source-of-truth.md`
7. **Every `POLICY` value it consumes matches the register** — not a nearby
   value, not a hardcoded one
8. Evidence attached: commands and their output

---

## 4. Check #7 is your most important job

**REQUIREMENT.** A builder under deadline who needs a tiebreak chain to finish
will invent a reasonable one. That silently converts a league decision into an
undocumented engineering default — which is exactly how the legacy system
acquired rules nobody agreed to.

**Every policy item now has a specified value** (`20_decisions.md` Part 2), so the
check is no longer "is it still empty." It is:

- **Does the implementation match the stated value?** Not a nearby one, not a
  more convenient one. Diff config against the register, item by item.
- **Is the value written into season config explicitly**, rather than hardcoded
  or supplied as a code fallback?
- **Does the system fail loudly when the key is absent?** A specified default is
  not a silent fallback. Delete a required key and confirm it refuses
  (`13_configuration.md` §6).
- **Where the register says a value is a DEFAULT rather than DECIDED**, confirm it
  is genuinely changeable at the stated cost — most claim "config edit."

**Ratified:** ADR-010 (score authority). **Narrowed, not closed:** O5 — verify the
four always-on requirements (detect, record both values, never two competing
official scores, provenance on override) are implemented regardless of the
finalisation setting.

---

## 5. Report format

For each finding:

```
WHAT      one sentence
WHERE     file:line, or the endpoint and payload
EVIDENCE  the command and its actual output
EXPECTED  the specification clause it violates, cited by document and section
SEVERITY  blocking | significant | minor
```

**REQUIREMENT.** Cite the specification clause. A finding without one is an
opinion about style, and should be labelled as such rather than mixed in with
defects.

**REQUIREMENT — report what you attacked and found nothing.** A clean area is
useful information only if the reader knows it was actually tested. Say what you
tried.

---

## 6. Rework limit — S31

**Three** meaningful failed fix/verify cycles on one piece, then **stop and
escalate** with a root-cause hypothesis and evidence.

Do not continue past three. In this project, the fourth attempt has historically
been a guess — a CI failure was chased twice on assumption before the actual step
name and log settled it in one pass.

---

## 7. What is out of scope for verification

Do not report as defects:

| Out of scope | Why |
|---|---|
| A `POLICY` slot carrying its registered value | That is correct behaviour. Report it only if the value **differs** from the register, or was hardcoded instead of configured |
| A DEFAULT you would have chosen differently | It is the league's call, not the verifier's. Raise it as a policy question, never as a defect |
| Phase 2 items — migration, Season 3, RecLeague | Deferred by decision (D1, D2, O10) |
| Missing offline tracker capture | Explicitly deferred (S7) |
| Absence of a user-facing change log | S25 — corrections are simple overwrites by product decision |
| Absence of in-app payments | S10/S11 — out of scope |
| Platform choice | O7 — Board decision, not an engineering defect |

**If you believe one of these is wrong, escalate it as a policy question**, not as
a bug. The distinction matters: bugs go to the builder, policy goes to the Board.
