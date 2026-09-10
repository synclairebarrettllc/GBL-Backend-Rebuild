# GBL Backend Rebuild

The new backend for the Good Basketball League — live stat tracking, standings,
scheduling, playoffs and registration.

**Status:** specification complete, implementation not started.

## Where to start

| You are | Read |
|---|---|
| **Building** | [`AGENTS.md`](AGENTS.md), then [`docs/spec/24_build-tasks.md`](docs/spec/24_build-tasks.md) |
| **Reviewing the design** | [`docs/spec/00_README.md`](docs/spec/00_README.md) |
| **Verifying a build piece** | [`docs/spec/23_verification-handoff.md`](docs/spec/23_verification-handoff.md) |
| **Wondering why a rule exists** | [`docs/spec/22_traceability.md`](docs/spec/22_traceability.md) |
| **Deciding league policy** | [`docs/spec/20_decisions.md`](docs/spec/20_decisions.md) |

## The specification

25 documents in [`docs/spec/`](docs/spec/). Every architectural rule traces to an
observed failure in the previous system and forward to a named test.

Every policy question has a value set, so nothing blocks the build. Values marked
**DEFAULT** are league policy and can be changed at any time — each one states
what changing it costs.

## Related

The previous system lives in `GBL-DOT-COM`. It is reference and evidence only —
it is still live and serving the league, and nothing here modifies it.
