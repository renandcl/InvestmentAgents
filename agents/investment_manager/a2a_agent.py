"""
Investment Manager A2A Agent (HTTP Coordination)

Uses A2AClientToolProvider to coordinate major workflow phases via HTTP.
"""

import logging
import os
import uuid
from datetime import datetime

from strands import Agent
from strands.a2a.a2a_client_tool_provider import A2AClientToolProvider
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from memory import MemoryService
from hook import SharedDocument

# Enable debug logs
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


def create_agent() -> Agent:
    """
    Create Investment Manager A2A agent for HTTP-based coordination.
    
    Coordinates workflow by calling major component coordinators via HTTP:
    - Port 9903: Analysts Coordinator
    - Port 9906: Research Manager
    - Port 9907: Trader
    - Port 9911: Risk Manager
    """
    model_id = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:7b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    ollama_model = OllamaModel(host=host, model_id=model_id)

    # Load system prompt
    with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
        system_prompt = f.read()

    current_date = datetime.now().strftime("%Y-%m-%d-%H-%M")
    session_manager = FileSessionManager(
        session_id=f"{current_date}_{uuid.uuid4()}",
        storage_dir="data/agents_sessions/investment_manager",
    )

    shared_document_file = "data/shared_document.json"
    memory = MemoryService(agent_id="investment_manager")
    shared_document_handler_hook = SharedDocument(shared_document_file, memory)

    # Configure A2A client to coordinate major components
    a2a_client_tool_provider = A2AClientToolProvider(
        agent_urls=[
            "http://localhost:9903/a2a",  # Analysts Coordinator
            "http://localhost:9906/a2a",  # Research Manager
            "http://localhost:9907/a2a",  # Trader
            "http://localhost:9911/a2a",  # Risk Manager
        ],
        llm=ollama_model,
    )

    agent = Agent(
        name="InvestmentManagerA2AAgent",
        agent_id="investment_manager_a2a",
        description="""Main orchestrator that coordinates the complete investment decision workflow.
        
        Sequentially executes phases:
        1. Analysis: Calls Analysts Coordinator (port 9903) for market intelligence
        2. Research: Calls Research Manager (port 9906) for bull/bear evaluation
        3. Trading: Calls Trader (port 9907) for execution plan
        4. Risk: Calls Risk Manager (port 9911) for risk evaluation and final decision
        5. Execution: Makes GO/NO-GO decision for actual execution
        
        Monitors shared state between phases to ensure proper sequencing.
        """,
        system_prompt=system_prompt,
        model=ollama_model,
        tool_providers=[a2a_client_tool_provider],
        session_manager=session_manager,
        hooks=[
            shared_document_handler_hook.get_shared_document,
            shared_document_handler_hook.add_prompt_reports,
            shared_document_handler_hook.save_shared_document,
        ],
    )

    return agent


if __name__ == "__main__":
    import asyncio

    async def test():
        agent = create_agent()
        
        # Test complete workflow
        workflow_request = """
        Execute complete investment workflow for AAPL on 2025-10-12:
        
        1. First, coordinate market analysis with Analysts Coordinator
        2. Then, coordinate research evaluation with Research Manager
        3. Next, coordinate trading plan with Trader
        4. Then, coordinate risk evaluation with Risk Manager
        5. Finally, make execution decision
        
        Ensure each phase completes before starting the next.
        """
        
        result = await agent.invoke(workflow_request)
        print("\n" + "="*60)
        print("INVESTMENT MANAGER A2A TEST RESULT:")
        print("="*60)
        print(result.text)

    asyncio.run(test())
