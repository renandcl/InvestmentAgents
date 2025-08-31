import logging

import uvicorn
from agent import FundamentalsAnalystAgent
from strands.multiagent.a2a import A2AServer

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


def a2a_agent_app():
    """Factory to create the FastAPI app for the fundamentals analyst agent."""
    fundamental_analyst = FundamentalsAnalystAgent()
    a2a_server = A2AServer(
        agent=fundamental_analyst.agent,
        host="0.0.0.0",
        port=9900,
    )
    return a2a_server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9900, log_level="info")
