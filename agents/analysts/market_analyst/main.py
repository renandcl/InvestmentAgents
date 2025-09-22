import logging

import uvicorn
from a2a.types import AgentSkill
from agent import MarketAnalyst
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the market analyst agent."""
    market_analyst = MarketAnalyst()
    skill = AgentSkill(
        description=market_analyst.agent.description,
        name=market_analyst.agent.name,
        id=market_analyst.agent.agent_id,
        tags=[],
        examples=["Provide the market analysis."],
    )
    a2a_server = A2AServer(
        agent=market_analyst.agent,
        host="0.0.0.0",
        port=9902,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9902, log_level="info")
