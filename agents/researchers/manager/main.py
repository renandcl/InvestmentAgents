import asyncio
import json
import logging

from agents.researchers.manager.agent import ResearchManager

# Enable debug logs
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)


async def test_research_manager():
    """Test the research manager agent."""
    
    # Load or create shared state
    ticker = "AAPL"
    date = "2025-10-12"
    
    # Example state with bull and bear reports
    state = {
        "ticker": ticker,
        "current_date": date,
        "market_report": "Strong upward trend with high volume...",
        "news_report": "Company announces new product line...",
        "fundamentals_report": "P/E ratio is favorable, revenue growing...",
        "bull_researcher_report": """
        Bull Analyst: Based on the market research, I see strong buy signals:
        1. Technical indicators show upward momentum
        2. Fundamentals are solid with growing revenue
        3. Recent news is very positive
        I recommend BUY.
        """,
        "bear_researcher_report": """
        Bear Analyst: I have concerns about this investment:
        1. Market valuation seems stretched
        2. Macroeconomic headwinds could impact growth
        3. Competition is intensifying
        I recommend SELL or HOLD.
        """,
        "bull_history": "Bull has argued for growth potential and strong fundamentals.",
        "bear_history": "Bear has highlighted risks and valuation concerns.",
    }
    
    with open("data/shared_state.json", "w") as f:
        json.dump(state, f)
    
    # Create and test the manager
    manager = ResearchManager()
    
    test_message = """
    Please evaluate the bull and bear analyses and provide your final investment recommendation.
    Make a decisive call based on the strongest arguments presented.
    """
    
    print("\n" + "="*80)
    print("TESTING RESEARCH MANAGER")
    print("="*80 + "\n")
    
    response = await manager.get_research_manager_decision(test_message)
    
    print("\n" + "="*80)
    print("MANAGER'S DECISION")
    print("="*80)
    print(response)
    print("\n")
    
    # Read updated state
    with open("data/shared_state.json", "r") as f:
        updated_state = json.load(f)
    
    if "research_manager_report" in updated_state:
        print("\n" + "="*80)
        print("SAVED REPORT IN SHARED STATE")
        print("="*80)
        print(updated_state["research_manager_report"])


if __name__ == "__main__":
    asyncio.run(test_research_manager())
