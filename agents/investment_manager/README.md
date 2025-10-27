# Investment Manager

The main orchestrator of the complete investment decision system. Coordinates all major workflow phases from analysis through risk evaluation to execution.

## Overview

The Investment Manager is the top-level coordinator that sequences and manages the entire investment decision workflow:

1. **Analysis Phase** - Coordinates market intelligence gathering
2. **Research Phase** - Evaluates investment opportunity
3. **Trading Phase** - Develops execution plan
4. **Risk Management Phase** - Evaluates risk and makes final decision
5. **Execution Phase** - Makes GO/NO-GO execution decision

## Architecture

### Coordinator Pattern

The Investment Manager follows the coordinator pattern with both:
- `agent.py` - Direct agent invocation for testing/development
- `a2a_agent.py` - HTTP coordination via A2A for production

### Workflow Sequencing

```
Investment Manager (Port 9912)
    ↓
    ├── 1. Analysis Phase → Analysts Coordinator (Port 9903)
    │       └── Returns: fundamentals_report, news_report, market_report
    │
    ├── 2. Research Phase → Research Manager (Port 9906)
    │       └── Returns: investment_plan, investment_recommendation
    │
    ├── 3. Trading Phase → Trader (Port 9907)
    │       └── Returns: trader_plan (entry, exit, risk params)
    │
    ├── 4. Risk Phase → Risk Manager (Port 9911)
    │       └── Returns: final_trade_decision (BUY/SELL/HOLD)
    │
    └── 5. Execution Phase → Investment Manager Decision
            └── Returns: execution_action, execution_status
```

## Components

### agent.py
Main implementation with direct agent coordination:
- `execute_analysis_phase()` - Coordinates analysts
- `execute_research_phase()` - Coordinates research
- `execute_trading_phase()` - Coordinates trader
- `execute_risk_phase()` - Coordinates risk management
- `make_execution_decision()` - Final execution approval
- `run_complete_workflow()` - End-to-end workflow execution

### a2a_agent.py
HTTP-based coordination using A2AClientToolProvider:
- Connects to ports: 9903, 9906, 9907, 9911
- Sequences HTTP calls to coordinator agents
- Manages state transitions via shared_document.json

### hook.py
Workflow state management:
- `get_shared_document()` - Loads workflow context
- `add_prompt_reports()` - Aggregates phase results
- `save_shared_document()` - Saves execution decisions

### memory.py
Persistent workflow memory:
- `add_workflow_memory()` - Stores completed workflows
- `search_similar_workflows()` - Finds similar past executions
- `get_workflow_statistics()` - Workflow performance metrics

### prompt.txt
System prompt defining:
- Orchestration responsibilities
- Phase sequencing rules
- Decision criteria (BUY/SELL/HOLD/REJECTED)
- State management approach

## Usage

### Start A2A Server

```bash
cd agents/investment_manager
python main.py
```

Server starts on port 9912.

### Test Complete Workflow (Standalone)

```bash
python agents/investment_manager/test_workflow.py
```

Runs complete workflow with all phases in-process (no HTTP servers needed).

### Test Individual Phases

```bash
python agents/investment_manager/test_workflow.py --phases
```

Tests each phase sequentially.

### Test via HTTP

```bash
python agents/investment_manager/test_a2a.py
```

Tests workflow via HTTP (requires all servers running).

### Programmatic Usage

```python
from agents.investment_manager.agent import InvestmentManager

manager = InvestmentManager()

# Run complete workflow
result = await manager.run_complete_workflow("AAPL", "2025-01-15")

print(f"Action: {result['execution_action']}")
print(f"Status: {result['execution_status']}")
```

## State Management

### Workflow State (shared_document.json)

```json
{
  "ticker": "AAPL",
  "current_date": "2025-01-15",
  "phase": "completed",

  "fundamentals_report": "...",
  "news_report": "...",
  "market_report": "...",

  "investment_plan": "...",
  "investment_recommendation": "...",

  "trader_plan": "...",

  "risk_debate_state": {
    "history": [...],
    "judge_decision": "..."
  },
  "final_trade_decision": "BUY...",

  "execution_action": "BUY",
  "execution_status": "APPROVED"
}
```

### Phase Transitions

1. **initialization** → Analysis starts
2. **analysis** → Research starts
3. **research** → Trading starts
4. **trading** → Risk management starts
5. **risk_management** → Execution decision
6. **completed** → Workflow done

## Decision Logic

### Execution Actions

- **BUY** - Strong positive signals, risk-adjusted approval
- **SELL** - Strong negative signals, risk necessitates exit
- **HOLD** - Conflicting signals or insufficient confidence
- **REJECTED** - Failed analysis or excessive risk

### Execution Status

- **APPROVED** - Ready for execution (BUY/SELL)
- **HOLD** - Wait for better conditions
- **REJECTED** - Do not execute

### Decision Criteria

1. **Analysis Quality** - Complete, accurate market intelligence
2. **Research Consensus** - Aligned bull/bear evaluation
3. **Trading Feasibility** - Clear execution plan with risk params
4. **Risk Assessment** - Balanced multi-perspective evaluation
5. **Confidence Level** - Sufficient conviction across all phases

## Integration Points

### Upstream (Coordinators Called)

- **Analysts Coordinator** (9903) - Market analysis
- **Research Manager** (9906) - Investment evaluation
- **Trader** (9907) - Execution planning
- **Risk Manager** (9911) - Risk evaluation

### Downstream (None)

Investment Manager is the top-level coordinator with no upstream callers in the workflow.

### External Systems (Future)

- Execution API - Submit approved orders
- Portfolio Management - Update positions
- Performance Tracking - Record outcomes
- Alerting - Notify stakeholders

## Configuration

### Environment Variables

```bash
OLLAMA_MODEL_ID=qwen2.5:7b          # Main model
OLLAMA_HOST=http://localhost:11434  # Ollama server
INVESTMENT_MANAGER_PORT=9912        # A2A server port
```

### Dependencies

Requires all coordinator agents to be available:
- Analysts Coordinator
- Research Manager
- Trader
- Risk Manager

## Memory & Learning

### Stored Patterns

- Past workflow executions
- Successful decision patterns
- Failed decision patterns
- Performance metrics by ticker/sector

### Learning Capabilities

- Identify successful decision characteristics
- Recognize failure patterns
- Adapt confidence thresholds
- Improve phase coordination

## Testing Strategy

### Unit Tests
- Individual phase execution
- State management hooks
- Memory operations
- Decision logic

### Integration Tests
- Multi-phase sequencing
- State transitions
- Error handling
- Timeout management

### End-to-End Tests
- Complete workflow execution
- Different market scenarios
- Various decision outcomes
- Performance under load

## Error Handling

### Phase Failures

If a phase fails:
1. Log error details
2. Update state with failure info
3. Optionally retry phase
4. Escalate to manual review if unrecoverable

### Timeout Management

Each phase has timeout limits:
- Analysis: 120s
- Research: 180s
- Trading: 90s
- Risk: 180s
- Execution: 30s

### Recovery Strategies

- Retry with exponential backoff
- Fallback to cached analysis
- Manual intervention workflow
- Circuit breaker pattern

## Monitoring

### Key Metrics

- Workflow completion rate
- Average execution time per phase
- Decision distribution (BUY/SELL/HOLD)
- Approval rate
- Error rates by phase

### Logging

- Phase transitions
- Coordinator responses
- State updates
- Decision rationale
- Execution outcomes

## Future Enhancements

1. **Parallel Analysis** - Run non-dependent phases concurrently
2. **Smart Routing** - Skip phases based on confidence
3. **Ensemble Decisions** - Multiple risk managers for consensus
4. **Real-time Updates** - Stream phase results as they complete
5. **Backtesting Integration** - Historical workflow simulation
6. **Performance Attribution** - Track decision quality over time

## Port Assignment

- **9912** - Investment Manager A2A Server

## See Also

- [Complete Workflow Documentation](../../COMPLETE_WORKFLOW.md)
- [Agent Architecture](../../AGENT_ARCHITECTURE.md)
- [Architecture Patterns](../../ARCHITECTURE_PATTERNS.md)
- [Agent Ports Reference](../../AGENT_PORTS_REFERENCE.md)
