"""Small services that can be tested without constructing an LLM agent."""

import json
import os
import re
import tempfile
from pathlib import Path
from string import Formatter
from typing import Any

from agents.hooks.contracts import AgentSpec, ContractError, MemoryPolicy


class PromptRenderer:
    def __init__(self, spec: AgentSpec):
        spec.validate()
        self.spec = spec
        self.template = spec.prompt_path.read_text(encoding="utf-8")
        fields = set()
        try:
            for _, name, format_spec, conversion in Formatter().parse(self.template):
                if name is None:
                    continue
                if not name.isidentifier() or format_spec or conversion:
                    raise ValueError(f"unsupported placeholder {name!r}")
                fields.add(name)
        except ValueError as exc:
            raise ContractError(f"{spec.agent_id}: invalid prompt: {exc}") from exc
        declared = {name for name, _ in spec.prompt_bindings}
        if fields != declared:
            raise ContractError(
                f"{spec.agent_id}: prompt bindings differ: "
                f"undeclared={sorted(fields - declared)}, "
                f"unused={sorted(declared - fields)}"
            )

    def render(self, context: dict[str, Any]) -> str:
        return self.template.format(**context)


class JsonReportStore:
    """Legacy JSON adapter; atomic replacement is not cross-process isolation."""

    def __init__(self, path: str):
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        snapshot = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict):
            raise ContractError("Shared document must be a JSON object")
        return snapshot

    def patch(self, changes: dict[str, str]) -> None:
        snapshot = self.read()
        snapshot.update(changes)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as output:
                temporary = Path(output.name)
                json.dump(snapshot, output, ensure_ascii=False)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def extract_report(message: dict[str, Any], agent_id: str) -> str:
    if message.get("role") != "assistant":
        raise ContractError(f"{agent_id}: report must be an assistant message")
    text = "\n".join(
        block["text"] for block in message.get("content", []) if "text" in block
    )
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if not text or "<think>" in text or "</think>" in text:
        raise ContractError(f"{agent_id}: empty report or incomplete think block")
    return text


def memory_query(policy: MemoryPolicy, snapshot: dict[str, Any]) -> str:
    return "\n".join(
        f"{label}: {snapshot.get(key)}" for label, key in policy.query_fields
    )


def format_memories(records: Any, empty_text: str) -> str:
    if isinstance(records, dict):
        records = records.get("results") or []
    elif not isinstance(records, list):
        records = []
    parts = []
    for number, record in enumerate(records, 1):
        if isinstance(record, dict) and (
            text := record.get("memory") or record.get("text")
        ):
            parts.append(f"Memory {number}:\n{text}\n\n")
    return "".join(parts) or empty_text
