# 16 — Security and Permissions

The system holds real personal data about real people, including minors, and
exposes an **anonymous write surface** by product design (S4). Those two facts
together set the security posture.

---

## 1. Actor model

| Actor | Identity | Can read | Can write |
|---|---|---|---|
| **Public** | none | published league data | nothing |
| **Tracker** | per-game capability token, **anonymous** | its own game's state | stat lines + status for **that game only** |
| **Admin** | authenticated account | everything | everything |
| **AI reader** | authenticated, read-only (S12) | published league data only | nothing |
| **Operator/deployer** | platform credentials | infrastructure | infrastructure |

**REQUIREMENT.** There is no role between public and admin in v1. If one is later
needed (a coach who edits only their roster), it is added as a **capability set**,
not as a second admin tier — tiered admin roles accumulate privileges nobody
audits.

---

## 2. The tracker token — an anonymous write surface, bounded

This is the most security-sensitive design decision in the system, because S4
requires courtside scorekeeping with **no login**.

The resolution is that the **token is the authorization and the game is the
scope**.

**REQUIREMENT — token properties:**

| Property | Requirement |
|---|---|
| Scope | exactly one `game_id`, bound at issuance |
| Capabilities | create/update/delete stat lines; `scheduled → in_progress`; submit to `completed` |
| Cannot | finalize, correct, touch rosters, touch the schedule, read or write any other game |
| Lifetime | expires at finalisation, or after a configured window, whichever is first |
| Entropy | cryptographically random, ≥128 bits |
| Revocation | an admin can revoke and reissue at any time |
| Storage | **hashed** at rest, like any credential |
| Transport | never in a query string — path segment or header only |

**REQUIREMENT.** No tracker endpoint accepts a `game_id` parameter
(`15_api.md` §5). The scope comes from the token, so there is no id to tamper
with. This is what reduces the anonymous surface to "can corrupt the game they
were given a link to" — which is the same risk as handing someone the scorebook.

**REQUIREMENT.** Tracker tokens are rate-limited per token.

### The S25 tension — flagged, not silently resolved

S25 states corrections are simple overwrites with **no audit trail required**.
Combined with S4 (anonymous tracker), a wrong stat has **no actor and no
history**.

**RECOMMENDATION — Board decision open (`20_decisions.md`).** Retain a minimal
internal write log **for the tracker surface only**: timestamp, token id,
previous value. Not a user-facing change-log — S25 governs the product surface.
The reason is operational: when a scorekeeper reports a wrong number, an
anonymous write path with no history cannot be debugged at all.

**If declined, the specification follows S25** and the tracker overwrites without
history. That is a legitimate call; it should be a made one.

---

## 3. Authentication

**REQUIREMENT.** Admin authentication uses a vetted library. No hand-rolled
password hashing, session generation, or token signing.

**REQUIREMENT.** Passwords are hashed with a memory-hard algorithm
(bcrypt/argon2/scrypt). Sessions are opaque, server-validated, HttpOnly, Secure,
SameSite, and expire.

**REQUIREMENT.** Failed logins are rate-limited and do not distinguish "no such
user" from "wrong password".

**REQUIREMENT — disabling an admin.** Deactivate; do not delete.

**Evidence (FACT).** Deleting a disposable admin account orphaned 24 `admin_logs`
rows. The FK said `ON DELETE CASCADE`, but the SQLite CLI has `foreign_keys`
**off by default**, so the delete silently left dangling references. The verified
backup caught it and refused the snapshot; the fix was restoring an inactive
placeholder, which preserves the history and returns `401` on login.

**REQUIREMENT.** `PRAGMA foreign_keys = ON` is asserted on every connection and
**tested** (`06_mutations.md` R8). A cascade that depends on a default that is
off is not a cascade.

---

## 4. Authorisation

**REQUIREMENT.** Authorisation is enforced by **route tree**, in middleware, not
per-handler. A handler added to `/api/admin/` is protected because of where it
lives.

**Evidence for why (FACT).** A per-handler discipline across a 8,373-line route
file is how 17 read sites came to miss a filter that 45 applied. Rules enforced
by remembering do not hold at scale.

**REQUIREMENT.** Middleware **denies by default**. An unmatched or newly added
route under a protected tree is protected before it is written.

**REQUIREMENT.** Every mutation re-checks authority at the service layer. Routes
are not the last line — they are the first.

---

## 5. Injection and input handling

**REQUIREMENT.** All SQL is parameterised. String-built SQL is prohibited, and a
static check enforces it.

**REQUIREMENT.** Every request body is validated against a schema at the boundary.
Unknown fields are rejected, not ignored — silently ignoring an unknown field is
how a client believes it wrote something it did not.

**REQUIREMENT.** Output is context-escaped. Team names, player names and sponsor
text are user-controlled and rendered on public pages.

**REQUIREMENT.** File uploads (sponsor images, S16) validate type and size
server-side, are stored outside the application origin or served with a
restrictive content type, and never execute.

---

## 6. Secrets

**REQUIREMENT — standing constraint.** **Zero credentials in source, commits,
client code, or logs.** Staging and production secrets are **fully separated**
(S28).

**REQUIREMENT.** Secrets come from the platform's secret store. A committed
secret is treated as compromised and rotated — not deleted from the file and
forgotten, because it remains in history.

**REQUIREMENT.** CI scans for committed secrets, and the pre-push gate runs it.

**REQUIREMENT — the repository stays private.** **FACT:** it contains a tracked
seed file with real player names.

---

## 7. Personal data

**REQUIREMENT.** Registration PII — phone, email, date of birth, emergency
contact, waiver artefacts — is **admin-only** and appears in no public response,
no AI-surface response (S12), no log line, no error payload, and no URL.

**REQUIREMENT.** Minors' data receives the same treatment with no exceptions, and
guardian signature records are stored with the same restriction.

**REQUIREMENT.** Logs record identifiers, not personal data. `player_id 412`, not
a name and phone number.

---

## 8. Dangerous operations

**REQUIREMENT.** Every destructive or bulk operation requires: an authenticated
admin, an explicit confirmation distinct from ordinary submission, a **dry run by
default**, and a **verified backup** where it touches historical data
(`14_import-migration.md` §7).

| Operation | Gate |
|---|---|
| Delete a game | Refused if stat lines exist; soft delete only |
| Bulk reschedule | Dry run first; atomic; full change set reported |
| Import / migration | Dry run first; verified backup; reconciliation |
| Config change | Validated; versioned |
| Delete a season | **Prohibited** — `RESTRICT` at the database level |
| Delete an admin | **Prohibited** — deactivate instead (FACT above) |

---

## 9. Deployment and agent boundaries

These are standing operational constraints, restated here because they are
security controls, not process preferences.

**REQUIREMENT.** **No direct agent pushes to production, ever.**

**REQUIREMENT (S27).** **One task = one branch = one PR.** No agent session works
directly on `main`.

**REQUIREMENT (S28).** Local → Staging → Production, separate credentials,
explicit release gate on production.

**REQUIREMENT (S29).** CI is a **mandatory** verification gate, not advisory.

**Evidence (FACT) — why these are security controls.** Two production outages in
this project came from the same root cause: code shipped ahead of the migrations
it depended on. The second took down public leaderboards and standings **while
the league owner was entering live stats**. The controls that now prevent it —
a migration guard wired to `prebuild`, a pre-push hook, CI — exist because
process discipline alone did not hold.

---

## 10. Rate limiting and abuse

**REQUIREMENT.** Rate limits on: public read endpoints, login attempts, tracker
token writes, and public registration submission.

**REQUIREMENT.** Registration is the highest-risk public write — it is
unauthenticated, creates rows, and captures PII. It is rate-limited per IP,
bot-resistant, and idempotent by `operation_id`.

---

## 11. Acceptance tests

| Test | Asserts |
|---|---|
| `sec.tree-auth` | A new route under `/api/admin/` is protected before any handler code |
| `sec.deny-by-default` | An unmatched protected route denies |
| `sec.tracker-scope` | A tracker token cannot read or write another game |
| `sec.tracker-no-escalation` | A tracker token cannot finalize, correct, or reach admin |
| `sec.tracker-expiry` | A token is rejected after finalisation and after revocation |
| `sec.token-hashed` | Tokens are not stored in plaintext |
| `sec.no-string-sql` | Static check: no string-built SQL |
| `sec.unknown-fields-rejected` | An unknown body field is rejected, not ignored |
| `sec.fk-pragma-on` | `PRAGMA foreign_keys` is ON for every connection |
| `sec.admin-delete-prohibited` | Deleting an admin is refused |
| `sec.no-pii-in-logs` | No log line contains a phone, email, or DOB |
| `sec.no-pii-in-errors` | No error payload contains PII |
| `sec.no-secrets-committed` | The secret scan passes on the full history |
| `sec.rate-limits` | Login, tracker, and registration enforce limits |
| `sec.session-flags` | Session cookies are HttpOnly, Secure, SameSite, expiring |
