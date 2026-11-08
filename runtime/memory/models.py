"""Validated JSON shapes for persistent memory snapshots."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemoryRecord(Model):
    memory: str = Field(pattern=r"\S")
    analysis_date: date


class MemorySource(Model):
    run_id: str
    sha256: str


class MemorySnapshot(Model):
    version: int
    run_id: str
    agent_id: str
    ticker: str
    analysis_date: date
    sources: list[MemorySource]
    memories: list[MemoryRecord]
