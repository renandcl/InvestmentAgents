"""
Test Investment Manager Complete Workflow (Standalone)

Tests the complete workflow using direct agent invocation.
No HTTP servers needed - runs all agents in-process.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.investment_manager.agent import InvestmentManager

# Enable debug logs
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def test_complete_workflow():
    """
    Test complete investment workflow end-to-end.

    This test runs the entire pipeline:
    1. Analysis Phase - gather market intelligence
    2. Research Phase - evaluate opportunity
    3. Trading Phase - develop execution plan
    4. Risk Phase - evaluate risk and decide
    5. Execution Phase - final GO/NO-GO decision
    """
    logger.info("\n" + "=" * 80)
    logger.info("INVESTMENT MANAGER - COMPLETE WORKFLOW TEST")
    logger.info("=" * 80 + "\n")

    # Initialize manager
    manager = InvestmentManager()

    # Test parameters
    ticker = "AAPL"
    date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"Ticker: {ticker}")
    logger.info(f"Date: {date}")
    logger.info("\nStarting workflow...\n")

    try:
        # Run complete workflow
        result = await manager.run_complete_workflow(ticker, date)

        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("WORKFLOW RESULTS")
        logger.info("=" * 80 + "\n")

        logger.info(f"Ticker: {result['ticker']}")
        logger.info(f"Date: {result['date']}")
        logger.info(f"Execution Action: {result['execution_action']}")
        logger.info(f"Execution Status: {result['execution_status']}")

        logger.info("\n" + "-" * 80)
        logger.info("PHASE SUMMARIES")
        logger.info("-" * 80 + "\n")

        for phase_name, phase_result in result["phases"].items():
            logger.info(f"{phase_name.upper()}: {phase_result[:200]}...")

        # Show final state
        logger.info("\n" + "-" * 80)
        logger.info("FINAL STATE")
        logger.info("-" * 80 + "\n")

        final_state = result.get("final_state", {})

        logger.info(f"Phase: {final_state.get('phase')}")
        logger.info(f"Execution Action: {final_state.get('execution_action')}")
        logger.info(f"Execution Status: {final_state.get('execution_status')}")

        # Show key decisions
        if final_state.get("final_trade_decision"):
            logger.info("\nFinal Trade Decision:")
            logger.info(final_state["final_trade_decision"][:500])

        logger.info("\n" + "=" * 80)
        logger.info("WORKFLOW TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80 + "\n")

        return result

    except Exception as e:
        logger.error(f"\n{'='*80}")
        logger.error("WORKFLOW TEST FAILED")
        logger.error(f"{'='*80}\n")
        logger.error(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


async def test_individual_phases():
    """
    Test each workflow phase individually.

    Useful for debugging specific phase issues.
    """
    logger.info("\n" + "=" * 80)
    logger.info("INVESTMENT MANAGER - INDIVIDUAL PHASE TESTS")
    logger.info("=" * 80 + "\n")

    manager = InvestmentManager()

    ticker = "NVDA"
    date = datetime.now().strftime("%Y-%m-%d")

    try:
        # Test Phase 1: Analysis
        logger.info("=" * 80)
        logger.info("PHASE 1: ANALYSIS")
        logger.info("=" * 80 + "\n")

        analysis_result = await manager.execute_analysis_phase(ticker, date)
        logger.info(f"Result: {analysis_result}\n")

        await asyncio.sleep(1)

        # Test Phase 2: Research
        logger.info("=" * 80)
        logger.info("PHASE 2: RESEARCH")
        logger.info("=" * 80 + "\n")

        research_result = await manager.execute_research_phase(
            f"Evaluate investment opportunity for {ticker}"
        )
        logger.info(f"Result: {research_result}\n")

        await asyncio.sleep(1)

        # Test Phase 3: Trading
        logger.info("=" * 80)
        logger.info("PHASE 3: TRADING")
        logger.info("=" * 80 + "\n")

        trading_result = await manager.execute_trading_phase(
            f"Develop trading plan for {ticker}"
        )
        logger.info(f"Result: {trading_result}\n")

        await asyncio.sleep(1)

        # Test Phase 4: Risk Management
        logger.info("=" * 80)
        logger.info("PHASE 4: RISK MANAGEMENT")
        logger.info("=" * 80 + "\n")

        risk_result = await manager.execute_risk_phase(
            f"Evaluate trading plan for {ticker} and provide final decision"
        )
        logger.info(f"Result: {risk_result}\n")

        await asyncio.sleep(1)

        # Test Phase 5: Execution
        logger.info("=" * 80)
        logger.info("PHASE 5: EXECUTION DECISION")
        logger.info("=" * 80 + "\n")

        execution_result = await manager.make_execution_decision()
        logger.info(f"Result: {execution_result}\n")

        # Show final state
        with open("data/shared_document.json", "r") as f:
            final_state = json.load(f)

        logger.info("=" * 80)
        logger.info("FINAL STATE AFTER ALL PHASES")
        logger.info("=" * 80 + "\n")
        logger.info(json.dumps(final_state, indent=2))

        logger.info("\n" + "=" * 80)
        logger.info("INDIVIDUAL PHASE TESTS COMPLETED")
        logger.info("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Individual phase test failed: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--phases":
        # Test individual phases
        asyncio.run(test_individual_phases())
    else:
        # Test complete workflow
        asyncio.run(test_complete_workflow())
