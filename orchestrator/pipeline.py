from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import Agent
from agents.registry import AGENT_CLASSES
from orchestrator.phase import Phase
from tools.registry import ToolRegistry
from workspace.shared import SharedWorkspace

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(
        self,
        phases: list[Phase],
        tool_registry: ToolRegistry,
        workspace: SharedWorkspace,
        max_workers: int = 4,
    ) -> None:
        self._phases = sorted(phases, key=lambda p: p.priority)
        self._registry = tool_registry
        self._workspace = workspace
        self._max_workers = max_workers
        self._completed_phases: set[str] = set()

    def _create_agent(self, role: str) -> Agent:
        cls = AGENT_CLASSES[role]
        return cls(tool_registry=self._registry, workspace=self._workspace)

    def _run_agent(self, role: str, task_description: str) -> tuple[str, str]:
        agent = self._create_agent(role)
        result = agent.run(task_description)
        return role, result

    def _check_dependencies(self, phase: Phase) -> bool:
        for dep in phase.depends_on:
            if dep not in self._completed_phases:
                return False
        return True

    def run(self, task_description: str) -> dict[str, dict[str, str]]:
        results: dict[str, dict[str, str]] = {}

        for phase in self._phases:
            logger.info(
                "=" * 60 + "\n Phase: %s [%s] — agents: %s\n" + "=" * 60,
                phase.name,
                phase.priority.name,
                ", ".join(phase.agent_roles),
            )

            if not self._check_dependencies(phase):
                logger.error(
                    "Phase '%s' dependencies not met: %s",
                    phase.name,
                    phase.depends_on,
                )
                break

            phase_results: dict[str, str] = {}
            start = time.time()

            if len(phase.agent_roles) == 1:
                role = phase.agent_roles[0]
                _, result = self._run_agent(role, task_description)
                phase_results[role] = result
            else:
                with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                    futures = {
                        pool.submit(self._run_agent, role, task_description): role
                        for role in phase.agent_roles
                    }
                    for future in as_completed(futures):
                        role = futures[future]
                        try:
                            _, result = future.result()
                            phase_results[role] = result
                        except Exception:
                            logger.exception("Agent %s failed", role)
                            phase_results[role] = f"ERROR: agent {role} failed"

            elapsed = time.time() - start
            logger.info(
                "Phase '%s' completed in %.1fs — %d agent(s)",
                phase.name,
                elapsed,
                len(phase.agent_roles),
            )

            results[phase.name] = phase_results
            self._completed_phases.add(phase.name)

        return results
