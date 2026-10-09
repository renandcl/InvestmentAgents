"""A2A server reserved for future distributed run isolation (port 9901)."""

from runtime.errors import UnsupportedExecutionMode

PORT = 9901


def a2a_agent_app():
    raise UnsupportedExecutionMode(
        "A2A servers are disabled until distributed run isolation is supported."
    )


if __name__ == "__main__":
    a2a_agent_app()
