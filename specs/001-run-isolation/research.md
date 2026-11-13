# Research and design decisions

**Reviewed:** 2026-10-08
**Inspected baseline:** c51be7f190f2ecd681290c207ac77e8a43d2f876
**Original proposal baseline:** a85931f

## Updates reviewed

| Commit | Delivered change | Impact on spec 001 |
|---|---|---|
| a78e134 | Dependency upgrade, memory API adjustments, model defaults and code-quality checks | Target current versions and preserve configuration tests |
| 7ec5032 | Explicit agent contracts and one shared hook lifecycle | Inject storage centrally; do not rewrite thirteen hook implementations |
| c51be7f | Participant-aware debates and shared round snapshots | Add transactional debate reset/round publication and run-bound context |

On 2026-10-08, git ls-remote origin refs/heads/master returned c51be7f190f2ecd681290c207ac77e8a43d2f876, matching local HEAD. This verifies the remote tip at review time without fetching or changing the working tree. The uncommitted run-isolation implementation is separate from that pushed baseline.

## Committed baseline evidence (c51be7f)

- main.py still resets data/shared_document.json and names reports by ticker/date; manager construction remains outside its try block.
- agents/hooks/contracts.py and specs.py now declare all thirteen agents' inputs, bindings, outputs/aliases and optional memory/debate policies.
- AgentLifecycleHooks centralizes prompt preparation, current-result extraction, output publication and subsequent memory writes. Per-agent hook.py files are thin selectors. The separate StoreMemoryHook was removed.
- JsonReportStore now uses a same-directory temporary file and os.replace. This prevents torn file replacement but still reads/modifies/replaces a whole shared document and can lose concurrent updates.
- DebateRunner resets participant/history/manager outputs at invocation start, stages contributions, publishes complete round reports/history together, then stores participant memories. Current reset/publication use JsonReportStore.patch, including remove_keys.
- RoundContext currently carries debate ID, phase, round, participant and a copied snapshot, but no run or manager-invocation identity. The new isolation boundary must validate those before consuming the snapshot.
- Research requires two participants per round; risk requires three. Both run opening/rebuttal/clarification and then one manager synthesis. Tool-result turns no longer count rounds.
- Participant messages are cleared at each invocation; manager messages at each debate. Preserve these resets inside any new invocation lock.
- Both trader_investment_plan and final_trade_decision are declared output aliases; research_debate_history and risk_debate_history are published state.
- Five memory adapters still share Chroma paths. Mem0 2.2.1 uses filters and top_k; its history_db_path still defaults to a user-level .mem0/history.db.
- Mutable provider caches, per-group session directories and manual MCP lifecycle still need run isolation.
- Distributed research/risk a2a_agent.py constructors already reject startup before side effects. Other distributed variants remain; servers wrapping in-process managers still use local participants under spec 003.
- AGENTS.md retains older descriptions of hook duplication/tool-turn rounds and must be updated during implementation alongside README.

## Dependency and validation evidence

Locked and installed versions checked locally: strands-agents 1.57.2, strands-agents-tools 0.8.9, mem0ai 2.2.1, chromadb 1.5.9 and pandas 3.0.6.

On 2026-10-08, .venv/Scripts/python.exe -B -m unittest discover -s tests -v passed all 39 tests: 6 regression, 15 hook-contract, 15 debate, 1 memory-configuration and 2 model-configuration tests. These validate the existing baseline, not the unimplemented isolation acceptance suite. No live provider/model was invoked.

The current pre-commit configuration includes Ruff/import sorting, Black, secret detection and file checks. No dependency upgrade is needed merely to revise this plan.

## Decisions retained and clarified

| Choice | Reason |
|---|---|
| SQLite per run | Transactional concurrent updates; JSON atomic replacement alone is insufficient |
| Explicit context through shared hooks/runner | Reuse implemented contracts and reject foreign staged snapshots |
| Dedicated debate operations | Manager publication crosses participant key ownership and requires quorum/history atomicity |
| Tombstone revisions + debate generations | Reset/deletion must not make stale callbacks valid again |
| OFF memory; run-only vector and history stores | Prevent hidden cross-run retrieval without redesigning temporal memory |
| Commit before memory | Preserve spec 002/003 behavior; no database rollback or exactly-once external-memory promise |
| Same-agent lifecycle serialization | Protect conversation clearing, direct invocation, streaming and hooks |
| All-A2A guard in isolated release | Retain original spec-001 scope; explicitly disclose its extension beyond spec 003 |
| Private caches; JSON export only; no resume | Original isolation architecture remains appropriate |

## Specification relationship

[Spec 002](../002-agent-hook-contracts/spec.md) supplies the shared contracts/lifecycle. [Spec 003](../003-participant-debates/spec.md) supersedes spec 002's old tool-turn debate policy. Spec 001 must preserve their current semantics while replacing persistence and injecting run ownership. It does not reopen their completed implementation tasks.

The artifact organization follows the [Spec Kit SDD workflow](https://github.com/github/spec-kit/blob/main/spec-driven.md). The update review changes the spec-001 Markdown package and progress record; it does not mark incomplete implementation tasks done.

The supplied investment-system PDF motivates run isolation/reproducibility in its architecture and P1/P2 roadmap. Later specifications still own temporal evidence, historical memory, full tracing/replay, distributed request context, resume, scheduling and financial simulation.

## Working-tree review findings (2026-10-08, now resolved)

- Runtime/context/store, agents/hooks/debates, memory workers, provider caches, root/standalone entry points and all A2A guards are now integrated locally. The previous foundation-only progress statement was stale.
- The review reran the offline suite: 88 tests in 26.456 seconds, 87 passed and one errored. The concurrent cache reader raises PermissionError in runtime/cache.py:read_text during Windows replacement. The existing bounded writer retry does not cover reads.
- Installed Strands 1.57.2, strands/tools/executors/_executor.py, converts raw tool exceptions to error ToolResultEvent values. RunRuntime.execute currently checks root completion and drains active invocations, while RunAgent removes finished invocations without retaining their failures. Static review therefore identifies an untested path where a child failure can be hidden by a later successful parent response. FR-010/FR-021 require a retained run-level failure and end-to-end acceptance coverage.
- utils/report.py still has a __main__ fallback reading data/shared_document.json. The runtime already has its own snapshot renderer; consolidate the supported reporting contract and migrate or guard the old demo.
- Real SDK tree/session execution, spawned independent runs, manager ownership, real fake-server MCP children, cancellation and hard-kill scenarios pass. Fake Mem0 workers validate worker configuration/protocol but do not establish actual installed Chroma retrieval isolation. The full acceptance matrix and pre-commit gate remain open.

Resolution on 2026-10-09: bounded cache-read retries, retained owned-agent failure
attribution, snapshot-only report rendering and all missing acceptance coverage
are implemented. Real installed Mem0/Chroma retrieval, history, vendor and entity
paths are now tested with offline inference substitutes. All 98 tests and quality
checks pass; evidence.md records the final requirement/scenario audit.
