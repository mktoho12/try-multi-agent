from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class SharedWorkspace:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._metadata: dict[str, dict] = {}
        self._current_iteration: int = 0
        self._changelog: list[dict] = []

    @property
    def root(self) -> Path:
        return self._root

    def set_iteration(self, n: int) -> None:
        self._current_iteration = n

    def get_iteration_changes(self, n: int) -> list[dict]:
        with self._lock:
            return [c for c in self._changelog if c["iteration"] == n]

    def write_file(self, rel_path: str, content: str, author: str = "unknown") -> None:
        full = self._root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        action = "update" if full.exists() else "create"
        with self._lock:
            full.write_text(content, encoding="utf-8")
            self._metadata[rel_path] = {
                "author": author,
                "updated_at": time.time(),
                "size": len(content),
            }
            if self._current_iteration > 0:
                self._changelog.append({
                    "iteration": self._current_iteration,
                    "path": rel_path,
                    "author": author,
                    "action": action,
                    "timestamp": time.time(),
                })

    def read_file(self, rel_path: str) -> str | None:
        full = self._root / rel_path
        if not full.exists():
            return None
        return full.read_text(encoding="utf-8")

    # Directories to exclude from listings and context summaries
    _EXCLUDE_DIRS = {
        "node_modules", ".next", "__pycache__", ".venv", "venv",
        ".git", ".mypy_cache", ".pytest_cache", "dist", "build",
    }

    def _is_excluded(self, path: Path) -> bool:
        return any(part in self._EXCLUDE_DIRS for part in path.parts)

    def list_files(self, pattern: str = "**/*") -> list[str]:
        return sorted(
            str(p.relative_to(self._root))
            for p in self._root.glob(pattern)
            if p.is_file() and not self._is_excluded(p.relative_to(self._root))
        )

    def get_context_summary(self) -> str:
        files = self.list_files()
        if not files:
            return "Workspace is empty. No artifacts have been created yet."
        lines = ["=== Current Workspace Artifacts ==="]
        if self._current_iteration > 0:
            lines.append(f"  [Iteration: {self._current_iteration}]")
        for f in files:
            meta = self._metadata.get(f, {})
            author = meta.get("author", "?")
            lines.append(f"  {f}  (by {author})")
        return "\n".join(lines)
