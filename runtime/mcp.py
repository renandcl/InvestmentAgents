"""Explicit provider environment and owned MCP acquisition."""

import os
import shutil

from dotenv import dotenv_values
from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient

from runtime.context import REPO_ROOT
from runtime.errors import RunContextMismatch

PROVIDERS = frozenset(
    {
        "yfin-market-data-server",
        "stockstats-market-data-server",
        "simfin-fundamentals-data-server",
        "finnhub-fundamentals-data-server",
        "finnhub-news-data-server",
        "reddit-news-data-server",
        "duckduckgo-news-data-server",
    }
)
RESERVED = ("INVESTMENT_RUN_ID", "INVESTMENT_CACHE_ROOT")


def server_parameters(runtime, provider, *, env_file=False):
    runtime.assert_running()
    if provider not in PROVIDERS:
        raise RunContextMismatch("Unregistered MCP provider")
    root = runtime.context.path("cache", provider)
    expected = {
        "INVESTMENT_RUN_ID": runtime.context.run_id,
        "INVESTMENT_CACHE_ROOT": str(root),
    }
    server = REPO_ROOT / "mcp-servers" / provider
    args = ["run"]
    if env_file:
        path = server / ".env"
        values = dotenv_values(path, interpolate=False) if path.exists() else {}
        if any(key in values and values[key] != expected[key] for key in RESERVED):
            raise RunContextMismatch(
                "Provider env file conflicts with host run context"
            )
        args.extend(["--env-file", str(path)])
    environment = dict(os.environ)
    environment.update(expected)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    for name in ("XDG_CACHE_HOME", "LOCALAPPDATA", "APPDATA"):
        environment[name] = str(runtime.context.path("cache", provider, "vendor"))
    for name in ("TMP", "TEMP", "TMPDIR"):
        environment[name] = str(runtime.context.path("cache", provider, "temporary"))
    args.append(str(server / "main.py"))
    root.mkdir(parents=True, exist_ok=True)
    runtime.context.path("cache", provider, "vendor").mkdir(exist_ok=True)
    runtime.context.path("cache", provider, "temporary").mkdir(exist_ok=True)
    uv = shutil.which("uv") or "uv"
    return StdioServerParameters(
        command=uv, args=args, env=environment, cwd=str(REPO_ROOT)
    )


def start_mcp(runtime, provider, *, env_file=False):
    parameters = server_parameters(runtime, provider, env_file=env_file)
    client = MCPClient(lambda: stdio_client(parameters))
    runtime.resources.register(lambda: client.stop(None, None, None))
    client.start()
    return client
