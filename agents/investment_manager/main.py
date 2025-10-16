"""
Investment Manager Main - A2A Server

HTTP server for Investment Manager coordination.
Port: 9912
"""

import logging
import os

from strands.a2a.a2a_http_server import serve_agent

# Enable debug logs
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)

if __name__ == "__main__":
    # Import after logging setup
    from a2a_agent import create_agent

    agent = create_agent()

    port = int(os.getenv("INVESTMENT_MANAGER_PORT", "9912"))

    print(f"\n{'='*60}")
    print(f"Starting Investment Manager A2A Server on port {port}")
    print(f"{'='*60}\n")

    serve_agent(agent, port=port)
