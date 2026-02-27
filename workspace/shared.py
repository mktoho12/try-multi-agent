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

    @property
    def root(self) -> Path:
        return self._root

    def write_file(self, rel_path: str, content: str, author: str = "unknown") -> None:
        full = self._root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            full.write_text(content, encoding="utf-8")
            self._metadata[rel_path] = {
                "author": author,
                "updated_at": time.time(),
                "size": len(content),
            }

    def read_file(self, rel_path: str) -> str | None:
        full = self._root / rel_path
        if not full.exists():
            return None
        return full.read_text(encoding="utf-8")

    def list_files(self, pattern: str = "**/*") -> list[str]:
        return sorted(
            str(p.relative_to(self._root))
            for p in self._root.glob(pattern)
            if p.is_file()
        )

    def get_context_summary(self) -> str:
        files = self.list_files()
        if not files:
            return "Workspace is empty. No artifacts have been created yet."
        lines = ["=== Current Workspace Artifacts ==="]
        for f in files:
            meta = self._metadata.get(f, {})
            author = meta.get("author", "?")
            lines.append(f"  {f}  (by {author})")
        return "\n".join(lines)
