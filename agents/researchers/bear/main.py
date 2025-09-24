import logging

import uvicorn
from a2a.types import AgentSkill
from agent import BearResearcher
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the bear researcher agent."""
    bear_researcher = BearResearcher()
    skill = AgentSkill(
        description=bear_researcher.agent.description,
        name=bear_researcher.agent.name,
        id=bear_researcher.agent.agent_id,
        tags=[],
        examples=["Provide the bear market analysis."],
    )
    a2a_server = A2AServer(
        agent=bear_researcher.agent,
        host="0.0.0.0",
        port=9904,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9904, log_level="info")
