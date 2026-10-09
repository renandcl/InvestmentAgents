# 001 - Run isolation

**Status:** Implemented and validated offline; prepared for pull-request review.
**Prepared:** 2026-10-04
**Reviewed:** 2026-10-09
**Inspected baseline:** c51be7f (original proposal: a85931f)

This package uses a specification -> design/contracts -> acceptance scenarios -> implementation tasks workflow, inspired by [GitHub Spec Kit](https://github.com/github/spec-kit/blob/main/spec-driven.md). It does not install Spec Kit or assume its commands are available.

Read in order:

1. [Specification](spec.md): scope, user stories and requirements.
2. [Plan](plan.md): architecture, integration and migration.
3. [Contracts](contracts.md): entities, APIs and lifecycle.
4. [Acceptance](acceptance.md): offline scenarios and requirement coverage.
5. [Tasks](tasks.md): implementation order and dependencies.
6. [Research](research.md): repository evidence and design decisions.

The update review incorporates [002 - hook contracts](../002-agent-hook-contracts/spec.md) and [003 - participant debates](../003-participant-debates/spec.md). Reuse the shared lifecycle and preserve complete-round publication; do not recreate per-agent hook logic. The revised package has 21 functional requirements, 27 acceptance scenarios and 24 implementation tasks.

Core decisions: explicit context; transactional state per run; isolated sessions, memory, caches and artifacts; memory OFF by default; owned-resource cleanup.

The first release supports in-process execution and standalone agent examples. The implementation guards all A2A entry points before side effects. The committed c51be7f baseline guards only the distributed research/risk variants and permits A2A servers wrapping local participants under spec 003. The broader restriction is an intentional compatibility change documented in the repository README and instructions.

The update review verified remote master and local HEAD at c51be7f. Its cache-read contention and SDK child-failure findings are resolved. Final verification passed 98 offline tests and the full pre-commit gate, including new files. See [acceptance evidence](evidence.md) for the scenario-by-scenario audit and [implementation progress](implementation-progress.md) for the delivered scope and limits.

Changes to behavior must first update the requirement and acceptance scenario. Implementation checkboxes remain unchecked until code and validation evidence exist. Historical data is not migrated. See implementation-progress.md for verified implementation evidence and remaining work.
