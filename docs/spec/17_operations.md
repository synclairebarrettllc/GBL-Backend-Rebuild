# 17 — Deployment and Operations

**Direction: PRESERVE the guards, BUILD FRESH everything else.** The migration
guard, pre-push hook and CI gate built late in the legacy system's life are kept
verbatim in spirit, because they exist as a direct consequence of two production
outages.

---

## 1. Environments — S28

| Environment | Purpose | Data | Credentials |
|---|---|---|---|
| **Local** | development | disposable | local only |
| **Staging** | verification before release | representative, non-production | staging-only |
| **Production** | the league | real | production-only, **fully separated** |

**REQUIREMENT (S28).** Staging and production secrets are fully separated. No
shared key, no shared database, no "staging points at prod for convenience."

**REQUIREMENT.** Production requires an **explicit release gate**. Merging to
`main` does not deploy to production by itself.

---

## 2. The migration ordering rule

**REQUIREMENT — the single most important operational rule in this document.**
**Migrations are applied before the code that depends on them. Always.**

**Evidence (FACT) — two production outages, one root cause.**

| Incident | What shipped early | Impact |
|---|---|---|
| 1 | `external_ref` reads before migrations 0027/0028 | Admin schedule down |
| 2 | `deleted_at` / `score_source` reads before migration 0029 | Public leaderboards and standings returned 500 **while the league owner was entering live stats** |

Both were caused by deploying code that queried columns the database did not yet
have. Neither was caught by review, because reviewing a diff does not tell you
what the production schema looks like.

**REQUIREMENT — enforced mechanically, not by discipline:**

1. **Migration guard** — a build-time check that refuses to build when
   `migrations/` is ahead of what has been applied. Wired to `prebuild`, so it
   cannot be skipped by forgetting.
2. **Skips cleanly when there is no local database**, so fresh clones and CI
   still build. A guard that breaks CI gets disabled, and a disabled guard
   protects nothing.
3. **Deploy order is: migrate, then deploy.** Never the reverse, never
   simultaneously.

**REQUIREMENT.** Migrations are forward-only, individually reversible where
possible, and never edited after being applied anywhere.

**REQUIREMENT — additive-first.** A column is added, backfilled, and read only
after the backfill completes. Drops happen in a later release than the code that
stopped using them. This is what makes the deploy order forgiving instead of
brittle.

---

## 3. The gate chain

Four gates, each catching what the previous one cannot.

| Gate | Runs | Catches |
|---|---|---|
| **`prebuild` migration guard** | every local build | schema/code skew |
| **Pre-push hook** | every push | migration skew, lint, build, script parse errors |
| **CI (S29)** | every PR | everything above, on a clean checkout |
| **Release gate** | production deploy | explicit human authorisation |

**REQUIREMENT (S29).** CI is **mandatory**, not advisory. A red check blocks the
merge.

**REQUIREMENT.** The pre-push hook is **tracked in the repository** and enabled
via `core.hooksPath`, so it is shared rather than reinvented per machine.

**Evidence (FACT).** The hook was proven by blocking a real push — a gate that
has never refused anything is untested.

### CI must run what the developer runs

**REQUIREMENT.** CI runs on a **clean checkout with no local database**, and its
steps match the local gates.

**Evidence (FACT).** The first CI configuration assumed the app lived in a
`webapp/` subdirectory when the git root *is* the app. It failed in six seconds.
A clean-clone reproduction locally passed all seven steps, which is precisely
why the fix had to come from the actual failing step name and log rather than
from another guess.

**REQUIREMENT — CI verifies the verifiers:**

- migrations apply cleanly to a **fresh** database
- the backup script **refuses a known-bad database**
- the secret scan passes over history

---

## 4. Branch and release discipline

**REQUIREMENT (S27).** **One task = one branch = one PR.** No session works
directly on `main`.

**REQUIREMENT — standing constraint.** **No direct agent pushes to production,
ever.**

**REQUIREMENT.** `main` is protected: no direct pushes, CI required, PR required.

**REQUIREMENT.** A PR states what it changes, which migrations it depends on, and
how it was verified. "Verified" means evidence — a command and its output — not
an assertion.

---

## 5. Backups

**REQUIREMENT.** Scheduled, automatic, verified backups of production, plus a
verified backup immediately before any migration or bulk operation
(`14_import-migration.md` §7).

**REQUIREMENT — verification criteria** (each exists because the first
implementation failed it):

| Check | Why |
|---|---|
| Taken via the SQLite online backup API, never `cp` | A file copy under WAL with an open writer is not a snapshot |
| `PRAGMA integrity_check` = `ok` | Structural corruption |
| `PRAGMA foreign_key_check` empty | Caught 24 orphaned rows in practice |
| Per-table row counts match source | The original loop `continue`d past missing tables and passed a table-less database |
| Content checksums match | The original compared two empty strings and called it a match |
| Non-empty floor | A snapshot of nothing is not a backup |
| WAL folded; no `-wal`/`-shm` sidecars | Verification itself created sidecars, making snapshots non-self-contained |
| **Failure discards the file** | A file that exists implies a backup exists |

**REQUIREMENT.** Restore is **tested**, on a schedule. An unrestored backup is a
hypothesis.

---

## 6. Observability

**REQUIREMENT (S26).** Errors surface visibly. Nothing fails silently.

**REQUIREMENT.** The admin dashboard flags **incomplete operational state** —
played games missing scores or stats, games stuck `in_progress`, imports with
unresolved conflicts.

**Evidence (FACT).** Game 1971 — five real stat lines, still reading
`scheduled 0-0` — was found months later during an audit. Nothing in the product
was looking. The dashboard flag is the fix.

**REQUIREMENT.** Structured logs carry identifiers, never PII
(`16_security.md` §7). Every log line for a mutation records the operation and
outcome.

**REQUIREMENT — health check.** A production endpoint that verifies the database
is reachable **and the applied migration version matches the deployed code's
expectation**. This is what would have turned both outages into a failed deploy
instead of a live incident.

---

## 7. Rollback

**REQUIREMENT.** Every release is rollback-capable. Because migrations are
additive-first, rolling back code does not require rolling back schema — which is
the property that makes rollback actually usable under pressure.

**REQUIREMENT.** A rollback is a **decision, not an improvisation**: revert the
deployment, verify the health check, then diagnose. Debugging in production while
the league is mid-game is how the second outage got worse.

---

## 8. Platform — O7, DECIDED

**Cloudflare Workers + D1 + Pages**, with **Durable Objects + WebSockets** for the
live tracker (`07_statistics.md` §5). Ratified — see `20_decisions.md` O7, which
is the authority for this value.

It survived bounded scrutiny: the real constraints (10GB D1 cap, single-writer
concurrency, transient errors needing retry) are not binding at GBL's scale, and
Cloudflare names live sports scores as the canonical Durable Objects use case.

**Gate G1's process produced this decision** — Claude Code recommended, the Board
ratified. The gate is closed; the outcome is above. Only the DDL dialect and the
real-time transport depend on it, but both are Stage 1 work, so a reversal after
Stage 1 is expensive.

---

## 9. Acceptance tests

| Test | Asserts |
|---|---|
| `ops.migration-guard-blocks` | A build with unapplied migrations fails |
| `ops.migration-guard-skips-clean` | A fresh clone with no database still builds |
| `ops.migrations-apply-fresh` | All migrations apply to an empty database |
| `ops.health-check-schema-version` | The health check fails when schema and code disagree |
| `ops.backup-rejects-corrupt` | A known-bad database is refused and no file is kept |
| `ops.backup-self-contained` | A verified snapshot has no `-wal`/`-shm` dependency |
| `ops.restore-tested` | A backup restores to a working database |
| `ops.secret-scan` | No credential in the working tree or history |
| `ops.ci-matches-local` | CI steps match the pre-push gate |
| `ops.main-protected` | Direct pushes to `main` are refused |
