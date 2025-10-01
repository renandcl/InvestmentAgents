import asyncio
import sys
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

async def run(ticker: str, start_date: str, end_date: str):
    server_params = StdioServerParameters(
        command="python",
        args=["reddit_mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Lista tools
            tools = await session.list_tools()
            print(f"Tools disponíveis: {[t.name for t in tools.tools]}")

            # Chama a tool com payload dinâmico
            result = await session.call_tool(
                "get_reddit_news",
                arguments={
                    "payload": {
                        "ticker": ticker,
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                },
            )

            if result.content:
                content = result.content[0]
                if isinstance(content, types.TextContent):
                    print("Resultado:", content.text)

def main():
    if len(sys.argv) != 4:
        print("Uso: uv run client.py <TICKER> <START_DATE> <END_DATE>")
        sys.exit(1)

    ticker, start_date, end_date = sys.argv[1:]
    asyncio.run(run(ticker, start_date, end_date))

if __name__ == "__main__":
    main()
