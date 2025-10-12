import logging

import uvicorn
from a2a.types import AgentSkill
from strands.multiagent.a2a import A2AServer

from agents.analysts.analysts_coordinator.a2a_agent import AnalystCoordinator

logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(format="%(levelname)s | %(name)s | %(message)s")


def a2a_agent_app():
    coordinator = AnalystCoordinator()
    skill = AgentSkill(
        description=coordinator.agent.description,
        name=coordinator.agent.name,
        id=coordinator.agent.agent_id,
        tags=[],
        examples=["Provide the analysis from all analysts of Agents."],
    )
    server = A2AServer(
        agent=coordinator.agent,
        host="0.0.0.0",
        port=9903,
        skills=[skill],
    )
    return server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9903, log_level="info")
