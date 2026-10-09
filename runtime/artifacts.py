"""Derived, atomically published exports; SQLite remains the authority."""

import hashlib
import json
import os
import subprocess
import time
from tempfile import NamedTemporaryFile

from agents.hooks.specs import AGENT_SPECS
from runtime.context import REPO_ROOT
from runtime.types import ArtifactRecord


def hash_file(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def provenance():
    def git(*args):
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    revision, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    return {
        "code_revision": revision,
        "dirty": bool(status) if status is not None else None,
        "lockfile_hash": hash_file(REPO_ROOT / "uv.lock"),
        "prompt_hashes": {
            agent: hash_file(REPO_ROOT / spec.prompt_path)
            for agent, spec in AGENT_SPECS.items()
        },
    }


def atomic_write(context, name, data):
    path = context.path(name)
    temporary = None
    try:
        with NamedTemporaryFile(mode="wb", dir=context.path(), delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Revalidate redirects just before publishing; host runs are trusted.
        deadline = time.monotonic() + 1.0
        while True:
            try:
                os.replace(temporary, context.path(name))
                break
            except PermissionError:
                # Windows readers can briefly deny delete sharing. Keep the old
                # complete file visible and retry only within a finite deadline.
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.005)
    finally:
        if temporary is not None:
            from pathlib import Path

            Path(temporary).unlink(missing_ok=True)
    return path


def render_report(values):
    parts = [
        f"# Investment Report for {values['ticker']} on {values['current_date']}",
        f"Run: {values['run_id']}",
    ]
    # One section per declared agent output; aliases are not duplicate sections.
    for spec in AGENT_SPECS.values():
        key = spec.output_keys[0]
        if key in values:
            parts.append(f"## {key.replace('_', ' ').title()}\n\n{values[key]}")
    return "\n\n".join(parts) + "\n"


def export_final(context, snapshot):
    # This is the proposed terminal view. Its presence is not proof of success:
    # commit_success must still verify the hash and commit the artifact receipts.
    values = dict(snapshot.values, status="SUCCEEDED")
    documents = (
        (
            "state",
            "shared_document.json",
            json.dumps(values, ensure_ascii=False, indent=2) + "\n",
        ),
        ("report", "report.md", render_report(values)),
    )
    artifacts = []
    for kind, name, text in documents:
        data = text.encode("utf-8")
        atomic_write(context, name, data)
        artifacts.append(
            ArtifactRecord(
                name,
                kind,
                hashlib.sha256(data).hexdigest(),
                len(data),
                snapshot.sequence,
            )
        )
    return artifacts


def refresh_manifest(store):
    record = store.inspect()
    atomic_write(
        store.context,
        "manifest.json",
        (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return record
