# from strands.multiagent import Swarm
from strands import Agent, tool
from strands.models.ollama import OllamaModel
from agents.analysts.market_analyst_agent.agent import MarketAnalystAgent
from agents.analysts.news_analyst_agent.agent import NewsAnalystAgent
from agents.analysts.fundamentals_analyst_agent.agent import FundamentalsAnalystAgent

import logging

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


# Agent initialization
model_id = "qwen3:8b"
host = "http://localhost:11434"
ollama_model = OllamaModel(
    host=host,
    model_id=model_id,
)

market_analyst = MarketAnalystAgent()
news_analyst = NewsAnalystAgent()
fundamentals_analyst = FundamentalsAnalystAgent()

@tool
def get_market_analyst_insights(message: str) -> str:
    """Get market analyst insights for a given message."""
    return market_analyst.agent(message)


def get_news_analyst_insights(message: str) -> str:
    """Get news analyst insights for a given message."""
    return news_analyst.agent(message)


def get_fundamentals_analyst_insights(message: str) -> str:
    """Get fundamentals analyst insights for a given message."""
    return fundamentals_analyst.agent(message)


analyst_coordinator = Agent(
    name="AnalystCoordinator",
    description="Coordinates the analysis of market, news, and fundamentals data to provide insights and recommendations.",
    system_prompt="You are an expert analyst coordinating the analysis of market, news, and fundamentals data to provide insights and recommendations.",
    tools=[
        get_market_analyst_insights,
        get_news_analyst_insights,
        get_fundamentals_analyst_insights,
    ],
    model=ollama_model,
)

prompt = """
Analyse AAPL

Discuss between the agents to come to a consensus on the best course of action.

Finally, provide a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** with a concise rationale in 1-2 sentences.
"""

result = analyst_coordinator(prompt)

print(result)

# # Create a swarm with these agents
# swarm = Swarm(
#     [
#         analyst_coordinator,
#         news_analyst.agent,
#         fundamentals_analyst.agent,
#         market_analyst.agent,
#     ],
#     max_handoffs=20,
#     max_iterations=20,
#     execution_timeout=900.0,  # 15 minutes
#     node_timeout=300.0,  # 5 minutes per agent
#     repetitive_handoff_detection_window=8,  # There must be >= 3 unique agents in the last 8 handoffs
#     repetitive_handoff_min_unique_agents=3,
# )

# result = swarm(prompt)

# print(result)
# # See which agents were involved
# for node in result.node_history:
#     print(f"Agent: {node.node_id}")
