# Task bundles

**Open one file. Build one task.** Each bundle carries the task, the
specification sections it needs, the decision values it must use, and the
incidents behind its rules — nothing else.

Generated from `docs/spec/` (44,945 words) by
`scripts/build-task-bundles.py`. **Do not edit these files** — edit the
specification and re-run the generator.

| Task | What | Stage | Words |
|---|---|---|---|
| [T1](./T1.md) | Stand up CI | Stage 0 | 817 |
| [T2](./T2.md) | Migration guard | Stage 0 | 751 |
| [T3](./T3.md) | Pre-push hook | Stage 0 | 734 |
| [T4](./T4.md) | Verified backup script | Stage 0 | 1,121 |
| [T5](./T5.md) | Static checks | Stage 0 | 551 |
| [T6](./T6.md) | Secret scanning | Stage 0 | 451 |
| [T7](./T7.md) | Branch protection | Stage 0 | 618 |
| [T8](./T8.md) | Core schema DDL | Stage 1 | 5,372 |
| [T9](./T9.md) | IdentityService | Stage 1 | 541 |
| [T10](./T10.md) | Season, Team, Roster, Venue, Config services | Stage 1 | 3,736 |
| [T11](./T11.md) | ScheduleService, individual operations | Stage 2 | 608 |
| [T12](./T12.md) | StatsService | Stage 2 | 1,424 |
| [T13](./T13.md) | GameResultService and the derivation edge | Stage 2 | 1,454 |
| [T14](./T14.md) | Finalisation and correction | Stage 2 | 1,512 |
| [T15](./T15.md) | Per-game capability tokens | Stage 3 | 1,137 |
| [T16](./T16.md) | Tracker write surface | Stage 3 | 1,163 |
| [T17](./T17.md) | Real-time propagation | Stage 3 | 1,158 |
| [T18](./T18.md) | StandingsService as a projection | Stage 4 | 915 |
| [T19](./T19.md) | Tiebreak chains | Stage 4 | 865 |
| [T20](./T20.md) | Seeds with basis snapshot | Stage 5 | 828 |
| [T21](./T21.md) | Bracket structure | Stage 5 | 1,234 |
| [T22](./T22.md) | Propagation and bounded correction | Stage 5 | 560 |
| [T23](./T23.md) | Public submission | Stage 6 | 470 |
| [T24](./T24.md) | Acceptance and assignment | Stage 6 | 516 |
| [T25](./T25.md) | Eligibility, waiver and PII | Stage 6 | 806 |
| [T26](./T26.md) | Schedule generation as a dry run | Stage 7 | 693 |
| [T27](./T27.md) | Bulk rescheduling | Stage 7 | 678 |
| [T28](./T28.md) | Public API | Stage 8 | 1,059 |
| [T29](./T29.md) | Admin dashboard | Stage 8 | 691 |
| [T30](./T30.md) | AI read surface | Stage 8 | 677 |
| [T31](./T31.md) | The full-season scenario | Stage 9 | 1,712 |

**Average bundle: 1,124 words** against a 44,945-word specification —
about 39x less to read per task.

## Not in any bundle

- `docs/spec/23_verification-handoff.md` — for whoever *verifies* a task,
  and that must not be the session that built it. It instructs the reader
  to attack the code rather than write it.
- `docs/spec/14_import-migration.md` — Phase 2, deferred (D1).

## If a bundle is not enough

The full specification is in `docs/spec/`. Start at `00_README.md`. If you
had to go there, say so in your report — it means the bundle was missing
something and the generator should be fixed.
