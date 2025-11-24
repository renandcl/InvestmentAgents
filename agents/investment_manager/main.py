import logging

import uvicorn
from a2a.types import AgentSkill
from agent import InvestmentManager
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the investment manager agent."""
    investment_manager = InvestmentManager()
    skill = AgentSkill(
        description=investment_manager.description,
        name=investment_manager.name,
        id=investment_manager.agent_id,
        tags=[],
        examples=["Execute complete investment workflow for AAPL on 2025-10-12."],
    )
    a2a_server = A2AServer(
        agent=investment_manager,
        host="0.0.0.0",
        port=9912,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9912, log_level="info")
