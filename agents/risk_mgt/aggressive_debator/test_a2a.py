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


async def send_sync_message(message: str, base_url: str = "http://localhost:9908"):
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
    
    # Create test state
    state = {
        "ticker": ticker,
        "current_date": date,
        "market_report": "Strong bullish momentum with RSI at 68. High volume breakout above resistance at $175.",
        "news_report": "Company announces breakthrough AI chip with 300% performance improvement. Analyst upgrades across the board.",
        "fundamentals_report": "P/E ratio: 28, Revenue growth: 15% YoY, Strong cash position: $60B, ROE: 18%.",
        "trader_decision": "BUY recommendation. Entry at $180, target $210 (16% upside), stop-loss at $170.",
        "risk_debate": {
            "history": "",
            "aggressive_last": "",
            "conservative_last": "",
            "neutral_last": "",
            "count": 0,
        },
    }

    with open("data/shared_document.json", "w") as f:
        json.dump(state, f)

    test_message = "Provide your aggressive risk analysis of this trading opportunity."
    asyncio.run(send_sync_message(test_message))
