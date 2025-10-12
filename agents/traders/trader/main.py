import logging

import uvicorn
from a2a.types import AgentSkill
from agent import Trader
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the trader agent."""
    trader = Trader()
    skill = AgentSkill(
        description=trader.agent.description,
        name=trader.agent.name,
        id=trader.agent.agent_id,
        tags=[],
        examples=["Execute the investment decision based on the plan."],
    )
    a2a_server = A2AServer(
        agent=trader.agent,
        host="0.0.0.0",
        port=9907,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9907, log_level="info")
