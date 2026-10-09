"""Unused service disabled until its run-context contract is implemented."""

from runtime.errors import UnsupportedExecutionMode

raise UnsupportedExecutionMode(
    "This unused service is disabled; use supported run-owned providers."
)
