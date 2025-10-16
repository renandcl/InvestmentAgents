"""
Aggressive Debator Agent

A risk analyst that champions high-reward, high-risk opportunities with bold strategies.
Leaf agent - does not coordinate other agents.
"""

import os
from strands import Agent
from hook import SharedStateHandler
from memory import MemoryService


class AggressiveDebator:
    """
    Aggressive/Risky Risk Analyst agent.
    
    Champions bold, high-reward opportunities and challenges conservative viewpoints
    with data-driven arguments for aggressive risk-taking strategies.
    """

    def __init__(self):
        # Load system prompt
        prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
        with open(prompt_path, "r") as f:
            system_prompt = f.read()

        # Initialize memory service
        self.memory_service = MemoryService()

        # Initialize state handler (hooks)
        state_handler = SharedStateHandler(self.memory_service)

        # Initialize agent
        self.agent = Agent(
            name="AggressiveDebator",
            agent_id="aggressive-debator",
            description="Risky Risk Analyst that champions high-reward, high-risk opportunities and bold trading strategies",
            system_prompt=system_prompt,
            model_name="ollama/qwen2.5:7b",
            model_url="http://localhost:11434",
            tools=[],  # Leaf agent - no sub-agents
            hooks=[
                state_handler.get_shared_state,
                state_handler.add_prompt_reports,
                state_handler.save_shared_state,
            ],
        )

    async def provide_aggressive_analysis(self, query: str) -> str:
        """
        Provide aggressive risk analysis.
        
        Args:
            query: The analysis request
            
        Returns:
            Aggressive risk perspective
        """
        return await self.agent.run(query)


# For testing
async def main():
    import asyncio
    
    debator = AggressiveDebator()
    result = await debator.provide_aggressive_analysis(
        "Provide your aggressive risk analysis of the trader's decision."
    )
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
