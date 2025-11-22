import logging

import uvicorn
from a2a.types import AgentSkill
from strands.multiagent.a2a import A2AServer

from agents.researchers.manager.agent import ResearchManager

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the research manager agent."""
    research_manager = ResearchManager()
    skill = AgentSkill(
        description=research_manager.description,
        name=research_manager.name,
        id=research_manager.agent_id,
        tags=[],
        examples=[
            "Provide your final investment recommendation based on the analyses."
        ],
    )
    a2a_server = A2AServer(
        agent=research_manager,
        host="0.0.0.0",
        port=9906,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9906, log_level="info")
