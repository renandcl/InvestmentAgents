import logging

from mcp import stdio_client, StdioServerParameters

from strands import Agent
from strands.models.ollama import OllamaModel
from strands.tools.mcp import MCPClient

logging.basicConfig(level=logging.INFO)


class AssetDataAgent:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host
        self.stdio_mcp_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=["run", "mcp-servers/asset-data-server/main.py"],
                )
            )
        )
        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

    async def invoke(self, message: str) -> str:
        # Create a Strands agent
        with self.stdio_mcp_client as mcp_client:
            tools = mcp_client.list_tools_sync()
            logging.info(f"Available tools: {tools}")

            agent = Agent(
                name="Asset Data Agent",
                description="Agent for retrieving asset data and history",
                system_prompt="You are an asset data retrieval agent.",
                tools=tools,
                model=self.ollama_model,
            )
            return await agent.invoke_async(message)
            


if __name__ == "__main__":
    agent = AssetDataAgent()
    test_message = "What is the current price of AAPL?"
    response = agent.invoke(test_message)
    print(f"Response: {response}")
    logging.info(f"Response: {response}")