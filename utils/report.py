"""Compatibility import for pure snapshot rendering; run exports own publication."""

from runtime.core.errors import UnsupportedExecutionMode
from runtime.core.types import StateSnapshot
from runtime.store.report import render_report


def generate_markdown_report(snapshot: StateSnapshot) -> str:
    """Render an explicit snapshot; RunRuntime owns paths, writes and receipts."""
    if not isinstance(snapshot, StateSnapshot):
        raise TypeError("An explicit StateSnapshot is required")
    return render_report(snapshot.values)


if __name__ == "__main__":
    raise UnsupportedExecutionMode("Use a managed run to export its final report")
