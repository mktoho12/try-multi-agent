"""Iterative orchestrator — build/review cycles with feedback convergence."""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import config
from agents.base import Agent, clear_agent_stats, print_agent_stats_summary
from agents.registry import AGENT_CLASSES
from orchestrator.iteration import FeedbackItem, IterationRecord, IterationScope
from tools.feedback import clear_store as clear_feedback_store
from tools.feedback import list_feedback
from tools.registry import ToolRegistry
from tools.server_manager import ServerManager
from workspace.shared import SharedWorkspace

logger = logging.getLogger(__name__)

ALL_BUILDERS = [
    "product_manager",
    "system_architect",
    "db_architect",
    "backend_engineer",
    "frontend_engineer",
]
BUILDER_PHASES = [
    ["product_manager"],                        # Phase 1: 要件定義
    ["system_architect", "db_architect"],        # Phase 2: 設計（並列）
    ["backend_engineer", "frontend_engineer"],   # Phase 3: 実装（並列）
]
ALL_REVIEWERS = [
    "operator",
    "it_systems",
    "code_reviewer",
    "test_engineer",
    "security_reviewer",
]
FINALIZATION_AGENTS = [
    "legal_agent",
    "tax_agent",
    "infra_engineer",
    "document_writer",
]


class IterativeOrchestrator:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        workspace: SharedWorkspace,
        max_iterations: int = 5,
        max_workers: int = 4,
    ) -> None:
        self._registry = tool_registry
        self._workspace = workspace
        self._max_iterations = max_iterations
        self._max_workers = max_workers
        self._history: list[IterationRecord] = []

    def _create_agent(self, role: str) -> Agent:
        cls = AGENT_CLASSES[role]
        return cls(tool_registry=self._registry, workspace=self._workspace)

    def _run_agent(self, role: str, task: str) -> tuple[str, str]:
        agent = self._create_agent(role)
        result = agent.run(task)
        return role, result

    def _plan_iteration(self, task_description: str, iteration: int) -> IterationScope:
        """Use the orchestrator agent to decide the scope for this iteration."""
        prompt_parts = [
            f"# イテレーション {iteration} のスコープ決定\n",
            f"## 元のタスク\n{task_description}\n",
            f"## 現在のイテレーション: {iteration}/{self._max_iterations}\n",
        ]

        if iteration == 1:
            prompt_parts.append(
                "## 指示\n"
                "これは初回イテレーションです。全ビルダーと全レビュアーを起動して、"
                "薄くても完全に動くシステムの骨格を作成してください。\n"
            )
        else:
            # Include previous feedback
            feedback_json = list_feedback(iteration=iteration - 1)
            prompt_parts.append(f"## 前回イテレーション({iteration - 1})のフィードバック\n```json\n{feedback_json}\n```\n")

            open_critical_major = list_feedback(status="open")
            prompt_parts.append(f"## 未解決の全フィードバック\n```json\n{open_critical_major}\n```\n")

            prompt_parts.append(
                "## 指示\n"
                "フィードバックを分析し、次のイテレーションのスコープを決定してください。\n"
                "- critical/major の未解決フィードバックがあれば、対象領域の builder を起動してください。\n"
                "- 全フィードバックが minor/suggestion のみなら action を 'converged' にしてください。\n"
            )

        prompt = "\n".join(prompt_parts)

        logger.info("[orchestrator] Planning iteration %d ...", iteration)
        agent = self._create_agent("orchestrator")
        raw_output = agent.run(prompt)

        return self._parse_scope(raw_output, iteration)

    def _parse_scope(self, raw_output: str, iteration: int) -> IterationScope:
        """Parse the orchestrator agent's JSON output into an IterationScope."""
        # Extract JSON from markdown code blocks or raw text
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_output, re.DOTALL)
        json_str = json_match.group(1) if json_match else raw_output

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("[orchestrator] Failed to parse scope JSON, using defaults for iteration %d", iteration)
            if iteration == 1:
                return IterationScope(
                    action="build",
                    builder_agents=list(ALL_BUILDERS),
                    reviewer_agents=list(ALL_REVIEWERS),
                    agent_instructions={},
                    focus_areas=["initial build"],
                )
            else:
                return IterationScope(action="converged")

        return IterationScope(
            action=data.get("action", "build"),
            builder_agents=data.get("builder_agents", []),
            reviewer_agents=data.get("reviewer_agents", []),
            agent_instructions=data.get("agent_instructions", {}),
            focus_areas=data.get("focus_areas", []),
            escalation_reason=data.get("escalation_reason", ""),
        )

    def _run_builders(
        self,
        task_description: str,
        scope: IterationScope,
        iteration: int,
    ) -> dict[str, str]:
        """Run selected builder agents in dependency order (BUILDER_PHASES)."""
        results: dict[str, str] = {}
        requested = set(scope.builder_agents)

        if not requested:
            logger.info("[iteration %d] No builders to run", iteration)
            return results

        logger.info(
            "[iteration %d] Running builders: %s",
            iteration,
            ", ".join(scope.builder_agents),
        )

        def build_task(role: str) -> str:
            parts = [task_description]
            instruction = scope.agent_instructions.get(role, "")
            if instruction:
                parts.append(f"\n\n# オーケストレーターからの指示\n{instruction}")
            if iteration > 1:
                fb = list_feedback(iteration=iteration - 1)
                parts.append(f"\n\n# 前回のフィードバック（参考）\n{fb}")
            return "\n".join(parts)

        for phase in BUILDER_PHASES:
            phase_roles = [r for r in phase if r in requested]
            if not phase_roles:
                continue

            logger.info("[iteration %d] Builder phase: %s", iteration, ", ".join(phase_roles))

            if len(phase_roles) == 1:
                role = phase_roles[0]
                _, result = self._run_agent(role, build_task(role))
                results[role] = result
            else:
                with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                    futures = {
                        pool.submit(self._run_agent, role, build_task(role)): role
                        for role in phase_roles
                    }
                    for future in as_completed(futures):
                        role = futures[future]
                        try:
                            _, result = future.result()
                            results[role] = result
                        except Exception:
                            logger.exception("[iteration %d] Builder %s failed", iteration, role)
                            results[role] = f"ERROR: builder {role} failed"

        return results

    def _run_reviewers(
        self,
        task_description: str,
        scope: IterationScope,
        iteration: int,
    ) -> dict[str, str]:
        """Run selected reviewer agents in parallel."""
        results: dict[str, str] = {}
        roles = scope.reviewer_agents

        if not roles:
            logger.info("[iteration %d] No reviewers to run", iteration)
            return results

        logger.info(
            "[iteration %d] Running reviewers: %s",
            iteration,
            ", ".join(roles),
        )

        def review_task(role: str) -> str:
            parts = [
                task_description,
                f"\n\n# レビュー指示\n"
                f"現在イテレーション {iteration} です。"
                f"ワークスペースの成果物をレビューし、submit_feedback ツールで "
                f"iteration={iteration} を指定してフィードバックを送信してください。",
            ]
            instruction = scope.agent_instructions.get(role, "")
            if instruction:
                parts.append(f"\n# オーケストレーターからの指示\n{instruction}")
            return "\n".join(parts)

        if len(roles) == 1:
            role = roles[0]
            _, result = self._run_agent(role, review_task(role))
            results[role] = result
        else:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {
                    pool.submit(self._run_agent, role, review_task(role)): role
                    for role in roles
                }
                for future in as_completed(futures):
                    role = futures[future]
                    try:
                        _, result = future.result()
                        results[role] = result
                    except Exception:
                        logger.exception("[iteration %d] Reviewer %s failed", iteration, role)
                        results[role] = f"ERROR: reviewer {role} failed"

        return results

    def _collect_feedback(self, iteration: int) -> list[FeedbackItem]:
        """Collect feedback items from the store for this iteration."""
        raw = json.loads(list_feedback(iteration=iteration))
        items = []
        for f in raw.get("feedback", []):
            items.append(
                FeedbackItem(
                    reviewer_role=f.get("reviewer_role", ""),
                    category=f.get("category", ""),
                    severity=f.get("severity", ""),
                    target_file=f.get("target_file", ""),
                    summary=f.get("summary", ""),
                    detail=f.get("detail", ""),
                    suggested_fix=f.get("suggested_fix", ""),
                )
            )
        return items

    def _run_validation(
        self,
        task_description: str,
        iteration: int,
    ) -> dict[str, str]:
        """Run runtime validation: start servers, execute validation agent, clean up."""
        if not config.ENABLE_RUNTIME_VALIDATION:
            return {}

        workspace_root = self._workspace.root
        server_mgr = ServerManager(workspace_root)

        backend_status = server_mgr.start_backend()
        frontend_status = server_mgr.start_frontend()

        server_context = (
            f"\n\n# サーバー状態\n"
            f"- Backend: {json.dumps(backend_status)}\n"
            f"- Frontend: {json.dumps(frontend_status)}\n"
        )
        browser_context = ""
        if config.ENABLE_BROWSER_VALIDATION:
            browser_context = (
                f"\n# ブラウザ検証\n"
                f"ブラウザツール (browser_navigate, browser_screenshot, browser_console_errors) が利用可能です。\n"
                f"バックエンドポート: {config.BACKEND_PORT}, フロントエンドポート: {config.FRONTEND_PORT}\n"
            )
        else:
            browser_context = (
                "\n# ブラウザ検証\n"
                "ブラウザツールは無効です。curl ベースの検証のみ行ってください。\n"
            )

        validation_task = (
            task_description
            + f"\n\n# ランタイム検証 (イテレーション {iteration})\n"
            f"ワークスペースの成果物を実行して検証してください。\n"
            f"submit_feedback で iteration={iteration}, reviewer_role='validation_engineer' を指定してください。"
            + server_context
            + browser_context
        )

        try:
            logger.info("[iteration %d] Running validation engineer", iteration)
            _, result = self._run_agent("validation_engineer", validation_task)
            return {"validation_engineer": result}
        finally:
            server_mgr.stop_all()
            if config.ENABLE_BROWSER_VALIDATION:
                try:
                    from tools.browser import shutdown_chrome
                    shutdown_chrome()
                except Exception:
                    pass

    def _run_finalization(self, task_description: str) -> dict[str, str]:
        """Run finalization agents (legal, tax, infra, docs) once."""
        logger.info("Running finalization agents: %s", ", ".join(FINALIZATION_AGENTS))
        results: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._run_agent, role, task_description): role
                for role in FINALIZATION_AGENTS
            }
            for future in as_completed(futures):
                role = futures[future]
                try:
                    _, result = future.result()
                    results[role] = result
                except Exception:
                    logger.exception("Finalization agent %s failed", role)
                    results[role] = f"ERROR: {role} failed"

        return results

    def _log_feedback_summary(self, feedback: list[FeedbackItem], iteration: int) -> None:
        """Log a summary of feedback for an iteration."""
        if not feedback:
            logger.info("[iteration %d] No feedback received", iteration)
            return
        counts = {"critical": 0, "major": 0, "minor": 0, "suggestion": 0}
        for f in feedback:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        logger.info(
            "[iteration %d] Feedback: %d critical, %d major, %d minor, %d suggestion",
            iteration,
            counts["critical"],
            counts["major"],
            counts["minor"],
            counts["suggestion"],
        )

    def run(self, task_description: str) -> dict[str, dict[str, str]]:
        """Run the iterative build/review loop."""
        clear_feedback_store()
        clear_agent_stats()
        results: dict[str, dict[str, str]] = {}

        for iteration in range(1, self._max_iterations + 1):
            self._workspace.set_iteration(iteration)
            logger.info("=" * 60)
            logger.info("  ITERATION %d / %d", iteration, self._max_iterations)
            logger.info("=" * 60)

            start = time.time()

            # 1. Plan
            scope = self._plan_iteration(task_description, iteration)
            logger.info(
                "[iteration %d] Scope: action=%s, builders=%s, reviewers=%s",
                iteration,
                scope.action,
                scope.builder_agents,
                scope.reviewer_agents,
            )

            if scope.action == "converged":
                logger.info("[iteration %d] Converged — all feedback is minor or below", iteration)
                break

            if scope.action == "escalate":
                logger.warning(
                    "[iteration %d] Escalation: %s",
                    iteration,
                    scope.escalation_reason,
                )
                results[f"iteration_{iteration}"] = {
                    "_escalated": scope.escalation_reason,
                }
                break

            # 2. Build
            build_results = self._run_builders(task_description, scope, iteration)
            results[f"iteration_{iteration}_build"] = build_results

            # 3. Review (static)
            review_results = self._run_reviewers(task_description, scope, iteration)
            results[f"iteration_{iteration}_review"] = review_results

            # 4. Runtime Validation
            validation_results = self._run_validation(task_description, iteration)
            if validation_results:
                results[f"iteration_{iteration}_validation"] = validation_results

            # 5. Collect feedback
            feedback = self._collect_feedback(iteration)
            self._log_feedback_summary(feedback, iteration)

            record = IterationRecord(
                number=iteration,
                build_results=build_results,
                feedback=feedback,
            )
            self._history.append(record)

            elapsed = time.time() - start
            logger.info("[iteration %d] Completed in %.1fs", iteration, elapsed)

        # Finalization
        logger.info("=" * 60)
        logger.info("  FINALIZATION")
        logger.info("=" * 60)
        finalization_results = self._run_finalization(task_description)
        results["finalization"] = finalization_results

        # Write feedback summary to workspace
        self._write_feedback_summary()

        # Print agent iteration usage summary
        print_agent_stats_summary()

        return results

    def _write_feedback_summary(self) -> None:
        """Write all feedback to a summary file in the workspace."""
        raw = json.loads(list_feedback())
        feedback_items = raw.get("feedback", [])
        if not feedback_items:
            return

        lines = ["# フィードバック一覧\n"]
        for f in feedback_items:
            lines.append(
                f"## [{f['severity'].upper()}] {f['summary']}\n"
                f"- レビュアー: {f['reviewer_role']}\n"
                f"- カテゴリ: {f['category']}\n"
                f"- 対象: {f.get('target_file', '(全般)')}\n"
                f"- ステータス: {f['status']}\n"
                f"- 詳細: {f['detail']}\n"
                f"- 改善案: {f.get('suggested_fix', '')}\n"
            )

        self._workspace.write_file(
            "review/feedback_summary.md",
            "\n".join(lines),
            author="orchestrator",
        )
