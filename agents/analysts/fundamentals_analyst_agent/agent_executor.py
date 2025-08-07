from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from agent import FundamentalsAnalystAgent
import logging

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
# Sets the logging format and streams logs to stderr
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)

class FundamentalsAnalystAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = FundamentalsAnalystAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        message = context.message
        inputText = message.parts[0].root.text
        result = await self.agent.invoke(inputText)
        logging.debug(f"Response: {result.message}")
        await event_queue.enqueue_event(new_agent_text_message(result.message["content"][0]["text"]))

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise Exception("cancel not supported")
