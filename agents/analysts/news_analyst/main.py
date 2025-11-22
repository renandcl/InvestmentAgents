import logging

import uvicorn
from a2a.types import AgentSkill
from agent import NewsAnalyst
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the news analyst agent."""
    news_analyst = NewsAnalyst()
    skill = AgentSkill(
        description=news_analyst.description,
        name=news_analyst.name,
        id=news_analyst.agent_id,
        tags=[],
        examples=["Provide the news analysis."],
    )
    a2a_server = A2AServer(
        agent=news_analyst,
        host="0.0.0.0",
        port=9901,
        skills=[skill],
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9901, log_level="info")
