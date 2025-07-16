import uvicorn

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from agent_executor import DataAgentExecutor

if __name__ == '__main__':
    skill = AgentSkill(
        id='data_extractor',
        name='Data Extractor',
        description='Extracts relevant data from various sources',
        tags=['data', 'extraction', 'investment'],
        examples=['extract market data', 'retrieve stock information for AAPL'],
    )

    # This will be the public-facing agent card
    public_agent_card = AgentCard(
        name='Data Extraction Agent',
        description='An agent that extracts relevant data from various sources',
        url='http://localhost:9900/',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=DataAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AFastAPIApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host='0.0.0.0', port=9900)
