# Runtime contracts

**Status:** Implemented; validated by the offline acceptance suite. Record-shaped return values below are Python dictionaries; snapshots, receipts, context and result values are dataclasses.

## Entities

| Entity | Fields and invariants |
|---|---|
| RunConfig | Nonempty bounded ticker; valid ISO current_date; memory_mode OFF/RUN_ONLY; resolved local output_root; execution_mode in_process; host-resolved model config |
| RunContext | schema_version=1; UUID4 lowercase hex run_id; ticker; current_date; UTC created_at; run_root and derived roots; immutable |
| RunRecord | Identity; status; started_at/finished_at; primary_error; cleanup_errors; provenance fields; unknown values explicit |
| ReportValue | Key, text, revision >=1, writer_agent_id, invocation_id, operation_id, UTC updated_at |
| WriteReceipt | Operation ID, canonical payload hash, resulting revisions, event sequence, duplicate flag |
| ArtifactRecord | Relative path, kind, SHA-256, byte length, generating state sequence |
| RunResult | Run ID, status, run_root/database path; report/state paths only if committed; warnings |
| RunEvent | Sequence, UTC time, event type, run/agent/invocation IDs and allowlisted payload |
| DebateRecord | Run/manager/invocation/debate IDs; generation; active/completed/aborted outcome; committed round index; policy identity |
| RoundContext | Existing phase/participant/snapshot plus run_id, manager_id, manager_invocation_id and snapshot revision; host-created, validated before use |
| RoundCommit | Complete participant contributions with their invocation/operation IDs, canonical full history, expected generation/round/revisions and one commit receipt |
| DebateHandle | Opaque host capability bound to run, manager, invocation, debate ID and generation; validated against the store |
| DebateStart | Handle plus atomic opening snapshot/revisions and idempotency receipt |
| RoundReceipt | Committed generation/round, resulting revisions, event sequence and duplicate flag |
| Tombstone | Deleted output key and monotonically increasing revision; prevents stale writes after reset |

current_date retains the current date-only meaning. It is not an evidence-availability cutoff. A later point-in-time contract owns as_of semantics.

Exported state contains run_id, schema_version, ticker, current_date, status, existing report keys and accepted research_debate_history/risk_debate_history. Preserve trader_investment_plan and final_trade_decision aliases. Identity cannot be changed by a report patch.

## Host API

```python
create_run(config: RunConfig) -> RunRuntime
runtime.context -> RunContext
runtime.store -> RunStore
runtime.memory_for(agent_id: str) -> MemoryAdapter
runtime.session_for(agent_id: str) -> FileSessionManager

store.read_snapshot() -> StateSnapshot
store.patch_reports(
    *,
    agent_id: str,
    invocation_id: str,
    operation_id: str,
    changes: dict[str, str],
    expected_revisions: dict[str, int],  # 0 means never written; deletions retain revisions
    debate_handle: DebateHandle | None = None,  # required for manager synthesis
) -> WriteReceipt
store.begin_debate(
    *, manager_id, manager_invocation_id, operation_id,
) -> DebateStart  # active generation + atomic reset snapshot/revisions
store.commit_round(
    *, debate_handle, operation_id, round_number, contributions,
    expected_revisions,
) -> RoundReceipt
store.validate_round(*, handle, participant_id, round_number, phase, snapshot)
store.end_debate(*, debate_handle, outcome) -> DebateRecord
store.transition(expected_status, next_status, *, error=None, cleanup_errors=()) -> RunRecord
store.commit_success(*, artifacts, required_report_key, expected_sequence) -> RunRecord
store.inspect() -> RunRecord

async runtime.execute(agent_factory, message, required_report_key) -> RunResult
```

RunStore is bound to exactly one context; callers cannot supply a different database/run path to a write. Identity and operation IDs are assigned by host code, never by model tools. create_run does not attach to or resume an existing run.

## Existing interfaces to preserve

AGENT_SPECS owns report keys, aliases, required/optional inputs, refresh policy, prompt bindings and debate/memory policy. Inject RunStore into AgentLifecycleHooks and DebateRunner instead of constructing JsonReportStore inside them. Per-agent hook files remain selectors. Preserve result ownership and valid stop-reason checks; a cached old assistant message cannot be finalized.

NullMemory satisfies the existing search_memories/add_memory interface without persistence. RUN_ONLY uses Mem0 2.2.1 entity filters and top_k with host-enforced run/agent scope.

## Debate operations

begin_debate derives reset keys from the manager's declared participant reports, history_key and output_keys; arbitrary model-supplied remove_keys are forbidden. Reject concurrent ownership of the same manager slot. In one transaction, verify RUNNING, claim a new generation, tombstone/reset its keys and return a consistent opening snapshot. Identical operation replay returns its original start receipt without clearing newly committed rounds.

commit_round verifies its handle belongs to this store/run, active manager invocation and expected round. Require exactly one valid nonempty contribution per configured participant. Preserve participant writer attribution while recording the manager as committer. Canonically construct accepted history from validated contributions; publish reports/history/round receipt atomically. The manager capability cannot touch unrelated reports or another debate's history.

Distinct manager slots have separate ownership/generation records. Guard manager synthesis with its active handle and all required committed rounds; ordinary patch_reports must not bypass this check. While a debate slot is active, ordinary participant patches to its report keys are rejected; only commit_round can publish them. Manager output patches require the matching handle and completed rounds. After synthesis or abort, close ownership. No automatic takeover of abandoned active handles.

Replay validation uses the canonical payload including run, manager, debate generation, round and contribution identities. A duplicate commit may return its historical receipt after a later reset but performs no writes, advances no round and triggers no external memory. Tombstone revisions never revert to zero.

Keep staging and delayed participant-memory behavior from spec 003. A post-commit memory error aborts synthesis and propagates run failure while keeping the committed round; external memory rollback/resume/exactly-once delivery remain out of scope.

## Patch algorithm

1. Validate registered agent and ownership of output keys.
2. Check operation ID. Identical committed replay returns its receipt; changed content/ownership fails.
3. Verify RUNNING and expected revisions for all changed keys.
4. Apply all changes and increment revisions in one transaction with receipt/event insertion.

Duplicate replay may return a receipt after terminal status, but cannot mutate anything. Any new operation on a terminal run fails RunNotWritable. A fresh agent invocation receives new invocation/operation IDs.

## Error contract

Reuse existing ContractError for malformed hook/debate contracts. New ownership/context failures may use RunContextMismatch, StateConflict or a documented subtype; UnsupportedExecutionMode should remain ContractError-compatible. Named runtime errors: InvalidRunConfig, RunAlreadyExists, RunContextRequired, RunContextMismatch, UnsafeRunPath, StateConflict, DuplicateOperationConflict, RunNotWritable, StateStoreUnavailable, UnsupportedExecutionMode, CleanupTimeout and RunExecutionError.

If allocation cannot establish durable storage, return an initialization error without claiming a persisted FAILED record. If outcome persistence later fails, expose run identity and outcome unknown. Cancellation remains cancellation after cleanup.

Persist error category/stage, safe messages and correlation IDs. Arbitrary exception strings and request bodies are not automatically safe. Any recorded endpoint omits credentials, query strings and fragments.

The runtime retains failures of owned agent invocations independently of SDK tool-result conversion. A parent model continuing after a child exception cannot clear that failure or authorize SUCCEEDED. Capture safe attribution before leaving the invocation boundary and check it before final artifact/status commit. Preserve committed reports/rounds after memory failure; do not retry external memory on receipt replay. This contract does not make all provider-level error results fatal when an agent otherwise completes successfully.

## Child process contract

- INVESTMENT_RUN_ID: host-generated validated identity.
- INVESTMENT_CACHE_ROOT: resolved absolute cache/<provider_id> root within that run.
- Missing/conflicting/invalid context rejects startup before service initialization.
- Run-specific environment is passed to the child only.
- Shared SimFin inputs are separate read-only paths.
- Standalone Mem0 MCP needs explicit run/agent vector/history locations or is disabled.
- Child lifetime belongs to the parent run; reuse across runs is forbidden.

## Status contract

| Trigger | Status |
|---|---|
| Root and owned agent invocations succeed + required root report + cleanup + artifact commit succeed | SUCCEEDED |
| Construction, invocation, required report, cleanup or final export fails | FAILED |
| Catchable cancellation | CANCELLED; cleanup errors retained |
| Hard kill or inability to persist outcome | Nonterminal/unknown; never inferred successful |

Artifact file presence alone is insufficient. SQLite owns status. A derived manifest can lag and be regenerated. New report writes and re-execution of a terminal run are prohibited.
