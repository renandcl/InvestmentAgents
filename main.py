import logging
from strands_tools.calculator import calculator
from strands import Agent
from strands.multiagent.a2a import A2AServer

logging.basicConfig(level=logging.INFO)

# Create a Strands agent
strands_agent = Agent(
    name="Calculator Agent",
    description="A calculator agent that can perform basic arithmetic operations.",
    tools=[calculator],
    callback_handler=None
)

# Create A2A server (streaming enabled by default)
a2a_server = A2AServer(agent=strands_agent)

# Start the server
a2a_server.serve()


def main():
    print("Hello from investmentagents!")


if __name__ == "__main__":
    main()
