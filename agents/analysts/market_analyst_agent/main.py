import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import MarketAnalystAgentExecutor

if __name__ == "__main__":
    skill = AgentSkill(
        id="market_analyst",
        name="Market Analyst",
        description="Analyzes market data and technical indicators to extract actionable insights",
        tags=["markets", "technical", "analysis", "trading"],
        examples=["analyze indicators for AAPL", "generate technical outlook for TSLA"],
    )

    public_agent_card = AgentCard(
        name="Market Analyst Agent",
        description="An agent that analyzes market data and technical indicators",
        url="http://localhost:9902/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=MarketAnalystAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AFastAPIApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host="0.0.0.0", port=9902)
