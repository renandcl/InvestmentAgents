"""A2A server reserved for future distributed run isolation (port 9909)."""

from __future__ import annotations

from typing import NoReturn

from runtime.errors import UnsupportedExecutionMode

PORT = 9909


def a2a_agent_app() -> NoReturn:
    raise UnsupportedExecutionMode(
        "A2A servers are disabled until distributed run isolation is supported."
    )


if __name__ == "__main__":
    a2a_agent_app()
