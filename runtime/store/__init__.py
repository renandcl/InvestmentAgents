"""Transactional run store."""

from runtime.store.base import TERMINAL, StoreBase, canonical
from runtime.store.debates import DebatesMixin
from runtime.store.reports import ReportsMixin


class RunStore(DebatesMixin, ReportsMixin, StoreBase):
    pass


__all__ = ["TERMINAL", "RunStore", "canonical"]
