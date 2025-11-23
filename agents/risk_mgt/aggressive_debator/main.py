import logging

import uvicorn
from a2a.types import AgentSkill
from agent import AggressiveDebator
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the aggressive debator agent."""
    debator = AggressiveDebator()
    skill = AgentSkill(
        description=debator.description,
        name=debator.name,
        id=debator.agent_id,
        tags=["risk", "aggressive", "trading"],
        examples=["Provide aggressive risk analysis of the trading decision."],
    )
    a2a_server = A2AServer(
        agent=debator,
        host="0.0.0.0",
        port=9908,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9908, log_level="info")
