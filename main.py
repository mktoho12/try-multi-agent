"""Multi-agent pipeline for sharehouse management system development."""

from __future__ import annotations

import logging
import sys

import config
from orchestrator.phase import Phase
from orchestrator.pipeline import PipelineOrchestrator
from orchestrator.task import Priority
from tools import create_tool_registry
from workspace.shared import SharedWorkspace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

PHASES = [
    Phase(
        name="requirements",
        priority=Priority.CRITICAL,
        agent_roles=["product_manager"],
        depends_on=[],
    ),
    Phase(
        name="design",
        priority=Priority.HIGH,
        agent_roles=["system_architect", "db_architect"],
        depends_on=["requirements"],
    ),
    Phase(
        name="implementation",
        priority=Priority.MEDIUM_HIGH,
        agent_roles=["backend_engineer", "frontend_engineer"],
        depends_on=["design"],
    ),
    Phase(
        name="review_and_test",
        priority=Priority.MEDIUM,
        agent_roles=["code_reviewer", "test_engineer", "security_reviewer"],
        depends_on=["implementation"],
    ),
    Phase(
        name="infrastructure",
        priority=Priority.MEDIUM,
        agent_roles=["infra_engineer"],
        depends_on=["implementation"],
    ),
    Phase(
        name="legal_compliance",
        priority=Priority.LOW,
        agent_roles=["legal_agent", "tax_agent"],
        depends_on=["requirements", "design"],
    ),
    Phase(
        name="documentation",
        priority=Priority.LOWEST,
        agent_roles=["document_writer"],
        depends_on=["implementation", "review_and_test"],
    ),
]

TASK_DESCRIPTION = """\
シェアハウス管理基幹システムを開発してください。

# システム概要
シェアハウスを複数物件運営する個人管理人のための業務管理システムです。

# 主要機能
1. 物件管理
   - 購入物件と賃貸物件（転貸）の区別
   - 物件ごとの取得価格・減価償却情報
   - 固定資産税・ランニングコスト管理

2. 部屋管理
   - 物件内の部屋一覧・入居状況表示
   - 部屋ごとの家賃単価設定

3. 住人管理
   - 住人基本情報（氏名・連絡先・緊急連絡先）
   - 入退去日・部屋割り管理
   - 入退去履歴の保持

4. 家賃管理
   - 月次家賃の設定・入金確認
   - 未入金アラート
   - 入金履歴の管理

5. 財務・税務
   - 収支管理（家賃収入 − 経費）
   - 減価償却の自動計算（定額法）
   - 確定申告用データ出力（不動産所得）
   - 経費記録（修繕費・管理費・水道光熱費等）

# 技術要件
- バックエンド: Python + FastAPI
- データベース: SQLite
- フロントエンド: Jinja2 テンプレート + シンプルな HTML/CSS/JS
- 単一管理人利用（マルチテナント不要）
- セキュリティ重視（個人情報・金融データの保護）
- 日本法準拠（借地借家法・個人情報保護法・所得税法）
"""


def main() -> None:
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)

    workspace = SharedWorkspace(config.WORKSPACE_DIR)
    tool_registry = create_tool_registry(workspace)

    orchestrator = PipelineOrchestrator(
        phases=PHASES,
        tool_registry=tool_registry,
        workspace=workspace,
    )

    logger.info("Starting multi-agent pipeline (%d phases)", len(PHASES))
    results = orchestrator.run(TASK_DESCRIPTION)

    logger.info("=" * 60)
    logger.info("Pipeline complete — results per phase:")
    for phase_name, agent_results in results.items():
        logger.info("  %s:", phase_name)
        for role, text in agent_results.items():
            preview = text[:100].replace("\n", " ") if text else "(empty)"
            logger.info("    %s: %s...", role, preview)

    logger.info("Artifacts written to: %s", config.WORKSPACE_DIR)


if __name__ == "__main__":
    main()
