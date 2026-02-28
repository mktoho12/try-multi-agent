"""Server lifecycle manager for runtime validation."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import config

logger = logging.getLogger(__name__)


class ServerManager:
    """Start / stop backend and frontend dev servers inside the workspace."""

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root
        self._processes: list[subprocess.Popen[bytes]] = []

    # ── public API ────────────────────────────────────────────────

    def start_backend(self) -> dict:
        """Start a uvicorn / FastAPI backend if main.py exists."""
        main_py = self._root / "src" / "backend" / "main.py"
        if not main_py.exists():
            main_py = self._root / "main.py"
        if not main_py.exists():
            return {"status": "skipped", "reason": "no main.py found"}

        # Prefer workspace venv python, fall back to system python
        venv_python = self._root / ".venv" / "bin" / "python"
        python = str(venv_python) if venv_python.exists() else shutil.which("python3") or "python3"

        port = config.BACKEND_PORT
        cmd = [
            python, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
        ]
        cwd = str(main_py.parent)
        return self._start_process("backend", cmd, cwd, port)

    def start_frontend(self) -> dict:
        """Start a Next.js / Vite frontend dev server if package.json exists."""
        pkg = self._root / "src" / "frontend" / "package.json"
        if not pkg.exists():
            return {"status": "skipped", "reason": "no frontend package.json found"}

        npm = shutil.which("npm") or "npm"
        port = config.FRONTEND_PORT
        cmd = [npm, "run", "dev", "--", "--port", str(port)]
        cwd = str(pkg.parent)
        return self._start_process("frontend", cmd, cwd, port, env_extra={"PORT": str(port)})

    def stop_all(self) -> None:
        """Terminate all managed processes."""
        for proc in self._processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._processes.clear()
        logger.info("[server_manager] All servers stopped")

    # ── internals ─────────────────────────────────────────────────

    def _start_process(
        self,
        label: str,
        cmd: list[str],
        cwd: str,
        port: int,
        env_extra: dict[str, str] | None = None,
    ) -> dict:
        import os

        env = {**os.environ, **(env_extra or {})}
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            self._processes.append(proc)
        except Exception as e:
            return {"status": "error", "reason": f"failed to start {label}: {e}"}

        # Health-check: poll for up to 10 seconds
        url = f"http://localhost:{port}/"
        if self._wait_for_http(url, timeout=10):
            logger.info("[server_manager] %s started on port %d", label, port)
            return {"status": "running", "port": port, "pid": proc.pid}

        # Server didn't respond — grab stderr for diagnostics
        stderr_snippet = ""
        if proc.stderr:
            try:
                stderr_snippet = proc.stderr.read1(4000).decode(errors="replace")  # type: ignore[attr-defined]
            except Exception:
                pass
        return {
            "status": "error",
            "reason": f"{label} did not respond within 10s",
            "stderr": stderr_snippet,
        }

    @staticmethod
    def _wait_for_http(url: str, timeout: int = 10) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urlopen(url, timeout=2)
                return True
            except (URLError, OSError):
                time.sleep(0.5)
        return False
