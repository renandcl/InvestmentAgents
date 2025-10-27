"""
Test Investment Manager via A2A HTTP

Tests complete workflow orchestration via HTTP calls.
"""

import asyncio
import json
import logging
from datetime import datetime

import httpx

# Enable debug logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_investment_manager_workflow():
    """
    Test complete investment workflow through Investment Manager.

    Tests the full pipeline:
    1. Analysis Phase
    2. Research Phase
    3. Trading Phase
    4. Risk Management Phase
    5. Execution Decision
    """
    base_url = "http://localhost:9912"

    # Test ticker and date
    ticker = "AAPL"
    date = datetime.now().strftime("%Y-%m-%d")

    workflow_request = f"""
    Execute complete investment decision workflow for {ticker} on {date}.

    Follow this sequence:

    1. ANALYSIS PHASE: Coordinate with Analysts Coordinator to gather comprehensive market intelligence
       - Wait for fundamentals, news, and market analysis to complete

    2. RESEARCH PHASE: Coordinate with Research Manager to evaluate opportunity
       - Ensure bull and bear perspectives are evaluated
       - Get investment recommendation

    3. TRADING PHASE: Coordinate with Trader to develop execution plan
       - Define entry points, position sizing, risk parameters

    4. RISK MANAGEMENT PHASE: Coordinate with Risk Manager for final evaluation
       - Facilitate multi-perspective risk debate
       - Get risk-adjusted decision (BUY/SELL/HOLD)

    5. EXECUTION DECISION: Make final GO/NO-GO decision
       - Review all phase results
       - Approve or reject for execution

    Ensure each phase completes before starting the next.
    Provide the final execution decision.
    """

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            logger.info(f"\n{'='*60}")
            logger.info("Testing Investment Manager Workflow")
            logger.info(f"Ticker: {ticker}")
            logger.info(f"Date: {date}")
            logger.info(f"{'='*60}\n")

            # Send workflow request
            logger.info("Sending workflow request to Investment Manager...")

            response = await client.post(
                f"{base_url}/a2a",
                json={
                    "message": workflow_request,
                    "context": {
                        "ticker": ticker,
                        "date": date,
                        "test_mode": True,
                    },
                },
            )

            if response.status_code == 200:
                result = response.json()

                logger.info(f"\n{'='*60}")
                logger.info("WORKFLOW COMPLETED")
                logger.info(f"{'='*60}\n")

                print(json.dumps(result, indent=2))

                # Load final state
                try:
                    with open("data/shared_document.json", "r") as f:
                        final_state = json.load(f)

                    logger.info(f"\n{'='*60}")
                    logger.info("FINAL EXECUTION STATE")
                    logger.info(f"{'='*60}")
                    logger.info(f"Ticker: {final_state.get('ticker')}")
                    logger.info(f"Date: {final_state.get('current_date')}")
                    logger.info(f"Action: {final_state.get('execution_action')}")
                    logger.info(f"Status: {final_state.get('execution_status')}")
                    logger.info(f"Phase: {final_state.get('phase')}")
                    logger.info(f"{'='*60}\n")

                except FileNotFoundError:
                    logger.warning("Could not load final state file")

            else:
                logger.error(f"Workflow failed: {response.status_code}")
                logger.error(response.text)

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        raise


async def test_phase_by_phase():
    """
    Test workflow by executing each phase individually.

    Useful for debugging specific phase issues.
    """
    base_url = "http://localhost:9912"
    ticker = "NVDA"
    date = datetime.now().strftime("%Y-%m-%d")

    phases = [
        {
            "name": "Analysis",
            "request": f"Execute analysis phase for {ticker} on {date}. Coordinate with Analysts Coordinator.",
        },
        {
            "name": "Research",
            "request": f"Execute research phase for {ticker}. Coordinate with Research Manager to evaluate opportunity.",
        },
        {
            "name": "Trading",
            "request": f"Execute trading phase for {ticker}. Coordinate with Trader to develop execution plan.",
        },
        {
            "name": "Risk Management",
            "request": f"Execute risk management phase for {ticker}. Coordinate with Risk Manager for final evaluation.",
        },
        {
            "name": "Execution",
            "request": f"Make execution decision for {ticker}. Review all prior phases and approve/reject.",
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            for i, phase in enumerate(phases, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"PHASE {i}: {phase['name']}")
                logger.info(f"{'='*60}\n")

                response = await client.post(
                    f"{base_url}/a2a",
                    json={"message": phase["request"]},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Phase {i} completed successfully")
                    print(json.dumps(result, indent=2)[:500])  # Print first 500 chars
                else:
                    logger.error(f"Phase {i} failed: {response.status_code}")
                    logger.error(response.text)
                    break

                # Wait between phases
                if i < len(phases):
                    await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Phase-by-phase test failed: {e}")
        raise


async def test_health_check():
    """Test that the Investment Manager server is running."""
    base_url = "http://localhost:9912"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/health")

            if response.status_code == 200:
                logger.info("✓ Investment Manager server is healthy")
                return True
            else:
                logger.error(f"✗ Health check failed: {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"✗ Cannot reach Investment Manager: {e}")
        return False


if __name__ == "__main__":
    import sys

    async def main():
        # Check server health first
        logger.info("Checking Investment Manager server health...")
        if not await test_health_check():
            logger.error("Investment Manager server is not running on port 9912")
            logger.error("Start it with: python agents/investment_manager/main.py")
            return

        # Choose test mode
        if len(sys.argv) > 1 and sys.argv[1] == "--phases":
            logger.info("\nRunning phase-by-phase test...\n")
            await test_phase_by_phase()
        else:
            logger.info("\nRunning complete workflow test...\n")
            await test_investment_manager_workflow()

    asyncio.run(main())
