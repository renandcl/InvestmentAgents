import asyncio
import logging
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5 minutes timeout


def create_message(*, role: Role = Role.user, text: str) -> Message:
    return Message(
        kind="message",
        role=role,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
    )


async def send_sync_message(message: str, base_url: str = "http://localhost:9907"):
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()

        config = ClientConfig(httpx_client=httpx_client, streaming=False)
        factory = ClientFactory(config)
        client = factory.create(agent_card)

        msg = create_message(text=message)

        async for event in client.send_message(msg):
            if isinstance(event, Message):
                logger.info(event.model_dump_json(exclude_none=True, indent=2))
                return event
            else:
                logger.info(f"Response: {str(event)}")
                return event


if __name__ == "__main__":
    import json

    ticker = "AAPL"
    date = "2025-10-12"
    
    # Create a complete test state with investment plan
    state = {
        "ticker": ticker,
        "current_date": date,
        "market_report": "Strong upward trend with high volume. RSI at 65, MACD showing bullish crossover.",
        "news_report": "Company announces new product line with strong pre-orders. Positive analyst coverage.",
        "fundamentals_report": "P/E ratio: 28.5, Revenue growth: 12% YoY, Strong balance sheet with $50B cash, ROE: 15%.",
        "investment_plan": """
        Based on comprehensive analysis:
        
        RECOMMENDATION: BUY
        
        Rationale:
        - Strong technical indicators showing momentum
        - Positive fundamental outlook with revenue growth
        - Recent product launch creates new revenue streams
        - Market sentiment is favorable
        
        Strategic Actions:
        1. Execute BUY order for target position
        2. Set stop-loss at 5% below entry
        3. Initial target: 15% upside based on analyst estimates
        4. Monitor earnings report in 2 weeks for potential position adjustment
        """,
        "judge_decision": "After evaluating both bull and bear arguments, I recommend BUY. The bull case is stronger with solid fundamentals and positive momentum outweighing short-term risks.",
    }

    with open("data/shared_document.json", "w") as f:
        json.dump(state, f)

    test_message = "Execute the investment decision with proper risk management parameters."
    asyncio.run(send_sync_message(test_message))
