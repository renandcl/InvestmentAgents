"""OFF does nothing; RUN_ONLY owns an isolated Mem0 worker per agent."""

import json
import os
import queue
import subprocess
import sys
import threading

from agents.hooks.contracts import ContractError
from runtime.context import REPO_ROOT, MemoryMode
from runtime.errors import RunContextMismatch


class NullMemory:
    def search_memories(self, current_situation, ticker, n_matches=2):
        return {"results": []}

    def get_memories(self):
        return {"results": []}

    def add_memory(self, memory, ticker):
        return None


def memory_config(root):
    return {
        "history_db_path": str(root / "history.sqlite3"),
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "agent_memories",
                "path": str(root / "chroma"),
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "qwen3:8b",
                "openai_base_url": "http://localhost:11434/v1",
                "api_key": "ollama",  # pragma: allowlist secret
            },
        },  # pragma: allowlist secret
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "embeddinggemma:latest",
                "openai_base_url": "http://localhost:11434/v1",
                "api_key": "ollama",  # pragma: allowlist secret
                "embedding_dims": 768,
            },
        },  # pragma: allowlist secret
    }


class RunMemory:
    def __init__(self, runtime, agent_id):
        self.runtime = runtime
        self.agent_id = agent_id
        self.process = None
        self._reader = None
        self._responses = queue.Queue()
        self._lock = threading.Lock()
        self._closed = False
        self.root = runtime.context.path("memory", agent_id)
        # Register before Popen/import/initialization, including partial startup.
        runtime.resources.register(self.close, abort=self.abort)
        self._start()

    def _start(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.runtime.context.path("memory", self.agent_id)
        environment = dict(os.environ)
        environment.update(
            {
                "INVESTMENT_RUN_ID": self.runtime.context.run_id,
                "MEM0_DIR": str(self.root / "vendor"),
                "MEM0_TELEMETRY": "false",
                "ANONYMIZED_TELEMETRY": "false",
                "PYTHONUTF8": "1",
            }
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "runtime.memory_worker",
                "--run-root",
                str(self.runtime.context.run_root),
                "--agent-id",
                self.agent_id,
            ],
            cwd=REPO_ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        process = self.process

        def read():
            try:
                for line in process.stdout:
                    self._responses.put(line)
            finally:
                self._responses.put(None)

        self._reader = threading.Thread(
            target=read, daemon=True, name="run-memory-response"
        )
        self._reader.start()
        self._request({"method": "initialize"})

    def _request(self, request):
        self.runtime.assert_running()
        with self._lock:
            if self._closed or self.process is None or self.process.poll() is not None:
                raise ContractError("Run memory worker is unavailable")
            try:
                self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
                line = self._responses.get(timeout=120)
                if line is None:
                    raise ValueError
                response = json.loads(line)
                if response.get("ok") is not True:
                    raise ValueError
                return response.get("result")
            except (OSError, ValueError, queue.Empty):
                self.abort()
                raise ContractError("Run memory operation failed") from None

    def _ticker(self, ticker):
        if ticker != self.runtime.context.ticker:
            raise RunContextMismatch("Memory ticker does not match its run")

    def add_memory(self, memory, ticker):
        self._ticker(ticker)
        return self._request({"method": "add", "memory": memory})

    def search_memories(self, current_situation, ticker, n_matches=2):
        self._ticker(ticker)
        if type(n_matches) is not int or not 1 <= n_matches <= 100:
            raise ContractError("Invalid memory result limit")
        return self._request(
            {"method": "search", "query": current_situation, "top_k": n_matches}
        )

    def get_memories(self):
        return self._request({"method": "get_all"})

    def abort(self):
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def close(self):
        if self._closed:
            return
        self._closed = True
        process = self.process
        if process is None:
            return
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.abort()
        finally:
            if self._reader is not None:
                self._reader.join(timeout=2)
            if process.stdout:
                process.stdout.close()


def create_memory(runtime, agent_id):
    if runtime.config.memory_mode == MemoryMode.OFF:
        return NullMemory()
    return RunMemory(runtime, agent_id)
