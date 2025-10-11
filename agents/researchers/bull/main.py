import logging

import uvicorn
from a2a.types import AgentSkill
from agent import BullResearcher
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the bull researcher agent."""
    bull_researcher = BullResearcher()
    skill = AgentSkill(
        description=bull_researcher.agent.description,
        name=bull_researcher.agent.name,
        id=bull_researcher.agent.agent_id,
        tags=[],
        examples=["Provide the bull market analysis."],
    )
    a2a_server = A2AServer(
        agent=bull_researcher.agent,
        host="0.0.0.0",
        port=9905,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9905, log_level="info")
