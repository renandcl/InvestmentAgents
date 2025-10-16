"""
Neutral Debator Agent

A risk analyst that prioritizes asset protection, stability, and low-risk strategies.
Leaf agent - does not coordinate other agents.
"""

import os
from strands import Agent
from hook import SharedStateHandler
from memory import MemoryService


class NeutralDebator:
    """
    Neutral/Neutral Risk Analyst agent.
    
    Protects assets through risk mitigation, emphasizes stability and security,
    and challenges overly aggressive positions with prudent counterarguments.
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
            name="NeutralDebator",
            agent_id="neutral-debator",
            description="Neutral/Neutral Risk Analyst that prioritizes asset protection, stability, and risk mitigation strategies",
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

    async def provide_neutral_analysis(self, query: str) -> str:
        """
        Provide neutral risk analysis.
        
        Args:
            query: The analysis request
            
        Returns:
            Neutral risk perspective
        """
        return await self.agent.run(query)


# For testing
async def main():
    debator = NeutralDebator()
    result = await debator.provide_neutral_analysis(
        "Provide your neutral risk analysis of the trader's decision."
    )
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
