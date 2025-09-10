import logging

import uvicorn
from a2a_agent import AnalystCoordinator
from strands.multiagent.a2a import A2AServer

logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(format="%(levelname)s | %(name)s | %(message)s")

def a2a_agent_app():
    coordinator = AnalystCoordinator()
    server = A2AServer(
        agent=coordinator.agent,
        host="0.0.0.0",
        port=9903,
    )
    return server.to_fastapi_app()


if __name__ == "__main__":
    uvicorn.run(a2a_agent_app(), host="0.0.0.0", port=9903, log_level="info")
