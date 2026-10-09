"""Distributed run-context propagation is not implemented in this release."""

from runtime.errors import UnsupportedExecutionMode


class InvestmentManager:
    def __init__(self, *args, **kwargs):
        raise UnsupportedExecutionMode(
            "A2A requires HTTP round-context propagation and distributed resource ownership; use the in-process agent."
        )


if __name__ == "__main__":
    InvestmentManager()
