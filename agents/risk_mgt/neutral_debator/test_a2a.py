import logging
from datetime import datetime
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5 minutes timeout


def create_message(*, role: Role = Role.user, text: str) -> Message:
    date_str = datetime.now().strftime("%Y%m%d%H%M%S")
    message_id = f"a2amsg-{date_str}{uuid4().hex[:8]}"
    return Message(
        kind="message",
        role=role,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=message_id,
    )


async def send_sync_message(message: str, base_url: str = "http://localhost:9910"):
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
    import asyncio

    test_message = "Provide your neutral risk analysis of this trading opportunity."
    asyncio.run(send_sync_message(test_message))
