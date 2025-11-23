import logging

import uvicorn
from a2a.types import AgentSkill
from agent import RiskManager
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the risk manager agent."""
    risk_manager = RiskManager()
    skill = AgentSkill(
        description=risk_manager.description,
        name=risk_manager.name,
        id=risk_manager.agent_id,
        tags=["risk", "management", "decision"],
        examples=[
            "Evaluate the trading decision from all risk perspectives and provide final recommendation."
        ],
    )
    a2a_server = A2AServer(
        agent=risk_manager,
        host="0.0.0.0",
        port=9911,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9911, log_level="info")
