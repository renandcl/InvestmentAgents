import logging
from strands.multiagent import Swarm
from bear.agent import BearResearcher
from bull.agent import BullResearcher

# Enable debug logs and print them to stderr
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# Create a swarm with these agents, starting with the researcher
swarm = Swarm(
    [BearResearcher(), BullResearcher()],
    entry_point=BearResearcher(),  # Start with the bear researcher
    max_handoffs=10,
    max_iterations=10,
    execution_timeout=900.0,  # 15 minutes
    node_timeout=300.0,       # 5 minutes per agent
    repetitive_handoff_detection_window=8,  # There must be >= 3 unique agents in the last 8 handoffs
    repetitive_handoff_min_unique_agents=3
)

# Execute the swarm on a task
result = swarm("Analyze the stock for a potential investment opportunity. Provide a final recommendation on whether to buy, hold, or sell the stock, along with a summary of the key points from both perspectives.")

# Access the final result
print(f"Status: {result.status}")
print(f"Node history: {[node.node_id for node in result.node_history]}")