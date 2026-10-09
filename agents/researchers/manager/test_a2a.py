"""Manual A2A client disabled for the isolated in-process milestone."""

from runtime.errors import UnsupportedExecutionMode


async def send_sync_message(message: str, base_url: str = "http://localhost:9906"):
    raise UnsupportedExecutionMode(
        "A2A clients require distributed run-context propagation."
    )


if __name__ == "__main__":
    raise UnsupportedExecutionMode(
        "A2A clients are disabled; use a fresh in-process run."
    )
