import asyncio
import os
import uuid
from datetime import datetime

from hook import SharedStateHandler
from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient

class SocialMediaAnalyst:
    def __init__(self, model_id="qwen3:4b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.stdio_mcp_reddit_news_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=["run", "mcp-servers/reddit-news-data-server/main.py"],
                )
            )
        )

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        # get system prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/social_media_analyst",
        )

        self.stdio_mcp_reddit_news_client.start()

        tools = (self.stdio_mcp_reddit_news_client.list_tools_sync())
        
        shared_state_file = "data/shared_state.json"
        shared_state_handler_hook = SharedStateHandler(shared_state_file)
        
        self.agent = Agent(
            name="SocialMediaAnalyst",
            agent_id="social_media_analyst",
            description="An agent that analyzes social media data to provide insights on market trends and sentiment.",
            system_prompt=self.system_prompt,
            model=self.ollama_model,
            tools=tools,
            session_manager=self.session_manager,
            hooks=[shared_state_handler_hook],
        )
    
    @tool
    async def run(self, query: str) -> AgentResult:
        """ Get data from social media for investment decisions by providing a ticker and date. """
        return await self.agent.invoke_async(query)


if __name__ == "__main__":
    import json
    
    state = {
        "ticker": "AAPL",
        "current_date": "2025-10-01",
    }
    with open("data/shared_state.json", "w") as f:
        json.dump(state, f)
    
    test_message = "Analyze the social media sentiment for AAPL on 2025-10-01."
    analyst = SocialMediaAnalyst()
    result = asyncio.run(analyst.run(test_message))
    print(result)