"""Prompt caching の動作検証スクリプト。

1エージェントにツール使用を誘発するタスクを投げて2-3回 API コールし、
cache_creation / cache_read の値を確認する。
max_iterations=3 なので 30秒程度で完了する。

Usage:
    uv run python scripts/test_caching.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from agents.backend_engineer import BackendEngineerAgent
from tools import create_tool_registry
from workspace.shared import SharedWorkspace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

if not config.ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY is not set. Check .env file.")
    sys.exit(1)

workspace = SharedWorkspace(config.WORKSPACE_DIR)
registry = create_tool_registry(workspace)

agent = BackendEngineerAgent(registry, workspace)
agent.max_iterations = 3

print("\n=== Prompt Caching Test ===")
print("ツール使用を含む2-3回の API コールで cache 動作を確認します\n")

# ツール使用（write_file）を誘発するタスク
agent.run("Create a file at test_cache_check.py with content: print('hello'). Then confirm it was created.")

print("\n=== 確認ポイント ===")
print("  Iter 1: cache_create > 0  → 初回キャッシュ作成")
print("  Iter 2+: cache_read > 0   → キャッシュヒット")
