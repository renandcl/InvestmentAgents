import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import FundamentalsAnalystAgentExecutor
import logging

# Configure the root strands logger
logging.getLogger("strands").setLevel(logging.DEBUG)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", 
    handlers=[logging.StreamHandler()]
)


if __name__ == "__main__":
    skill = AgentSkill(
        id="fundamentals_analyst",
        name="Fundamentals Analyst",
        description="Analyzes and extracts fundamental financial data",
        tags=["finance", "analysis", "investment"],
        examples=["analyze financial statements", "extract key metrics for AAPL"],
    )

    # This will be the public-facing agent card
    public_agent_card = AgentCard(
        name="Fundamentals Analyst Agent",
        description="An agent that analyzes and extracts fundamental financial data",
        url="http://localhost:9900/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=FundamentalsAnalystAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AFastAPIApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host="0.0.0.0", port=9900)
