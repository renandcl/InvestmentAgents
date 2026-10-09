import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.errors import UnsupportedExecutionMode

raise UnsupportedExecutionMode(
    "This unused provider is disabled for the run-isolation milestone."
)
