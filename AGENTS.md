# AGENTS.md

Multi-agent investment analysis system built on **Strands Agents**. Given a ticker and a date, a tree of LLM agents produces analyst reports, a bull/bear debate, a trading plan, a risk debate and a final decision, and the results are written to a Markdown report.

## Commands

```bash
uv sync --all-packages          # install root + all mcp-servers workspace packages
uv run --env-file .env main.py  # batch run: assets × dates configured in main.py:main()
uv run python -B -m unittest discover -s tests -v  # offline acceptance
uv run pre-commit run --all-files  # Ruff/import sorting, Black, secret/file checks
```

- Always run commands from the **repo root**. Imports are absolute. Runtime roots resolve from the repository; each run writes under `data/runs/<uuid>/` by default, with no parent CWD/environment switching.
- No code calls `load_dotenv`. Root `.env` values reach the process only through `uv run --env-file .env` or the shell. MCP servers that need keys get their own `--env-file mcp-servers/<server>/.env` from the agent that spawns them.
- Tests use unittest, temporary directories, offline models/providers and owned subprocesses. Never call live models/providers to replace acceptance tests. A2A manual clients now reject execution.
- Each agent/memory `__main__` uses `runtime.examples.run_example` to allocate a fresh managed run. Example: `uv run --env-file .env python -m agents.traders.trader.agent --ticker AAPL --date 2025-08-01 --memory-mode OFF`.

## Runtime requirements

- Every agent defaults to an OpenAI-compatible endpoint at `http://localhost:11434/v1` (Ollama) with model `qwen3:8b`. You can override this for each group with `{ANALYSTS,RESEARCHERS,TRADERS,RISK_MANAGERS,INVESTMENT_MANAGER}_{BASE_URL,API_KEY,MODEL_ID}` (see `.env.example`).
- Memory defaults to OFF with no vendor initialization. RUN_ONLY uses an owned Mem0 worker per run/agent, with private Chroma/history/vendor stores and run/agent filters. Its existing Ollama settings (`qwen3:8b`, `embeddinggemma:latest`, 768 dims) do not use agent-group environment overrides. Never import Mem0 in the parent or switch a parent MEM0_DIR.
- Some MCP servers need API keys (`FINNHUB_API_KEY`, `REDDIT_CLIENT_ID/SECRET`, `SIMFIN_API_KEY`). Some also need data downloaded beforehand with `mcp-servers/<server>/data/download_data.py`.

## Architecture

The orchestration is hierarchical, and every sub-agent is exposed as a tool of its parent:

```
InvestmentManager (agents/investment_manager)
├── AnalystCoordinator ── FundamentalsAnalyst, NewsAnalyst, MarketAnalyst
├── ResearchManager ───── BullResearcher, BearResearcher        (memory)
├── Trader                                                      (memory)
└── RiskManager ───────── Aggressive/Conservative/Neutral debators (memory)
```

### Per-agent file convention

Every agent directory follows the same layout. When you add or change an agent, keep all of these files in sync:

| File | Role |
|---|---|
| `agent.py` | `RunAgent` subclass requiring keyword-only `runtime=`; pass the same runtime to all in-process children. Public tools invoke through the shared whole-lifecycle gate. |
| `a2a_agent.py` | Orchestrator compatibility entry point; rejects construction before side effects. |
| `main.py` | Reserved A2A factory/port; rejects execution until distributed run ownership is specified. |
| `hook.py` | Thin `AgentLifecycleHooks` selector for an immutable `AGENT_SPECS` contract. |
| `prompt.txt` | Format template validated against contract bindings; double literal braces. Keep financial prompts unchanged for isolation work. |
| `memory.py` | Thin adapter to `runtime.memory_for(agent_id)`; never instantiate a global Mem0 store. |
| `test_a2a.py` | Reserved manual client; rejects before network or legacy state access. |

`main.py` (root) uses the **in-process** path inside `RunRuntime.execute`. All A2A paths are disabled, including servers that previously wrapped local participants. Keep their ports unchanged.

### A2A ports

| Port | Agent | Port | Agent |
|---|---|---|---|
| 9900 | fundamentals_analyst | 9906 | research_manager |
| 9901 | news_analyst | 9907 | trader |
| 9902 | market_analyst | 9908 | aggressive_debator |
| 9903 | analysts_coordinator | 9909 | conservative_debator |
| 9904 | bear researcher | 9910 | neutral_debator |
| 9905 | bull researcher | 9911 | risk_manager |
| | | 9912 | investment_manager |

If you change a port, update `main.py`, `test_a2a.py`, and the parent's `a2a_agent.py`.

### State flow: `data/runs/<run_id>/run.sqlite3`

Agents coordinate through their bound transactional `RunStore`:

1. Validate immutable `RunConfig`, exclusively allocate UUID storage and persist CREATED before model/MCP/memory construction. Start RUNNING inside the managed lifecycle.
2. Shared hooks load consistent snapshots and declared defaults. Host-bound round contexts reject foreign/stale state before prompts or memory lookup.
3. Python schedules opening/rebuttal/clarification with every participant. Stage a full quorum against the same prior-round snapshot, commit reports/history together, then store memory. Reset keys atomically, fence old generations and synthesize once after all rounds. Tool turns/retries never count as rounds.
4. Successful current results publish declared outputs/aliases with expected revisions and operation receipts. Memory follows commit; duplicate receipts never retry memory. An owned-agent failure remains fatal even if the SDK turns it into a tool error.
5. Drain work, close owned resources, export UTF-8 state/report, then commit artifact hashes and SUCCEEDED. JSON/manifest are derived; SQLite owns status. Propagate failures with run identity and batch nonzero status. Hard kills do not imply success or authorize resume.

`AGENT_SPECS` owns report keys and aliases. Runtime rendering uses those declarations; `utils/report.py` accepts an explicit snapshot and never reads a global file. Sessions live under `sessions/<agent_id>/<session_id>/` within the run. Preserve legacy data; no read fallback, import, migration or deletion. `JsonReportStore` remains only for isolated legacy-adapter tests.

### MCP servers (`mcp-servers/`)

Each MCP server is a uv workspace member built on FastMCP with a `models/` (pydantic params) + `services/` layout, and is started over stdio by the agents through `uv run [--env-file ...] mcp-servers/<name>/main.py`:

- market_analyst → `yfin-market-data-server`, `stockstats-market-data-server`
- fundamentals_analyst → `simfin-fundamentals-data-server`, `finnhub-fundamentals-data-server`
- news_analyst → `finnhub-news-data-server`, `reddit-news-data-server`, `duckduckgo-news-data-server`
- `google-news-data-server` and `mem0-server` are unused and reject startup.

Register cleanup before acquisition; close only owned handles in reverse order, including partial starts/cancellation. MCP children get validated INVESTMENT_RUN_ID/INVESTMENT_CACHE_ROOT through their explicit environment. Use hashed cache keys and atomic replacement with bounded Windows read/write retries. SimFin CSV inputs remain read-only. Never route run state through parent globals.

## Known quirks

- There is no Social Media Analyst; risk contracts retain a missing-report default.
- Shared contracts/lifecycle and `runtime/` own isolation behavior. Preserve their boundaries instead of copying storage logic into agents. Update specs/001-run-isolation requirements and acceptance before changing behavior; specs 002/003 define inherited hook/debate semantics.
- Each agent configures logging on its own, with a mix of DEBUG and INFO for `strands`.
