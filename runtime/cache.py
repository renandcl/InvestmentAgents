"""Private provider caches with hashed argument keys and atomic publication."""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from agents.hooks.contracts import ContractError
from runtime.artifacts import atomic_write
from runtime.context import contained, validate_run_id
from runtime.errors import RunContextMismatch, RunContextRequired, UnsafeRunPath
from runtime.store import canonical


class CacheCorruption(ContractError):
    pass


@dataclass(frozen=True)
class ProviderContext:
    run_id: str
    provider_id: str
    root: Path

    def __post_init__(self):
        validate_run_id(self.run_id)
        if not re.fullmatch(r"[a-z0-9-]+", self.provider_id):
            raise RunContextMismatch("Invalid provider identity")
        if (
            not self.root.is_absolute()
            or self.root.name != self.provider_id
            or self.root.parent.name != "cache"
            or self.root.parent.parent.name != self.run_id
        ):
            raise RunContextMismatch("Provider root does not match run identity")
        contained(self.root)

    def path(self, *parts):
        return contained(self.root, *parts)


def provider_context(provider_id):
    run_id, root = os.environ.get("INVESTMENT_RUN_ID"), os.environ.get(
        "INVESTMENT_CACHE_ROOT"
    )
    if not run_id or not root:
        raise RunContextRequired("Provider requires explicit host run/cache context")
    return ProviderContext(run_id, provider_id, Path(root))


class RunCache:
    def __init__(self, context):
        self.context = context
        context.path().mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_run(cls, runtime, provider_id):
        return cls(
            ProviderContext(
                runtime.context.run_id,
                provider_id,
                runtime.context.path("cache", provider_id),
            )
        )

    @classmethod
    def for_provider(cls, provider_id):
        return cls(provider_context(provider_id))

    def key(self, method, arguments, *, extension="json"):
        if extension not in {"json", "csv"}:
            raise UnsafeRunPath("Unsupported cache format")
        payload = {
            "provider": self.context.provider_id,
            "version": 1,
            "method": method,
            "arguments": arguments,
        }
        return (
            hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
            + "."
            + extension
        )

    def path(self, key):
        if not re.fullmatch(r"[a-f0-9]{64}\.(json|csv)", key):
            raise UnsafeRunPath("Cache filenames must be hashed keys")
        return self.context.path(key)

    def read_text(self, key):
        deadline = time.monotonic() + 1.0
        while True:
            try:
                return self.path(key).read_text(encoding="utf-8")
            except FileNotFoundError:
                return None
            except PermissionError:
                # Windows replacement can briefly deny opening the old file.
                # Persistent permission errors remain errors, never cache misses.
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.005)
            except UnicodeError:
                raise CacheCorruption("Cache is not UTF-8") from None

    def write_text(self, key, text):
        self.path(key)
        atomic_write(self.context, key, text.encode("utf-8"))

    def read_json(self, key):
        text = self.read_text(key)
        if text is None:
            return None
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                raise ValueError
            return data
        except (ValueError, TypeError):
            raise CacheCorruption("Invalid provider cache record") from None

    def write_json(self, key, data):
        self.write_text(key, json.dumps(data, ensure_ascii=False, allow_nan=False))


def service_cache(provider_id, cache=None):
    if cache is None:
        return RunCache.for_provider(provider_id)
    if not isinstance(cache, RunCache) or cache.context.provider_id != provider_id:
        raise RunContextMismatch("Wrong provider cache")
    cache.context.path()
    return cache


def configure_yfinance(cache):
    # yfinance's process-level singleton caches are safe only inside its owned
    # one-run provider process; never switch them in the application process.
    if provider_context(cache.context.provider_id) != cache.context:
        raise RunContextMismatch("YFinance must run in its owned provider process")
    import yfinance

    path = cache.context.path("vendor", "yfinance")
    path.mkdir(parents=True, exist_ok=True)
    yfinance.set_tz_cache_location(str(path))
