from __future__ import annotations

from typing import TYPE_CHECKING

from agents.product_manager import ProductManagerAgent
from agents.system_architect import SystemArchitectAgent
from agents.db_architect import DBArchitectAgent
from agents.backend_engineer import BackendEngineerAgent
from agents.frontend_engineer import FrontendEngineerAgent
from agents.infra_engineer import InfraEngineerAgent
from agents.code_reviewer import CodeReviewerAgent
from agents.test_engineer import TestEngineerAgent
from agents.security_reviewer import SecurityReviewerAgent
from agents.legal_agent import LegalAgent
from agents.tax_agent import TaxAgent
from agents.document_writer import DocumentWriterAgent
from agents.orchestrator_agent import OrchestratorAgent
from agents.operator_agent import OperatorAgent
from agents.it_systems_agent import ITSystemsAgent
from agents.validation_engineer import ValidationEngineerAgent

if TYPE_CHECKING:
    from agents.base import Agent

AGENT_CLASSES: dict[str, type[Agent]] = {
    "product_manager": ProductManagerAgent,
    "system_architect": SystemArchitectAgent,
    "db_architect": DBArchitectAgent,
    "backend_engineer": BackendEngineerAgent,
    "frontend_engineer": FrontendEngineerAgent,
    "infra_engineer": InfraEngineerAgent,
    "code_reviewer": CodeReviewerAgent,
    "test_engineer": TestEngineerAgent,
    "security_reviewer": SecurityReviewerAgent,
    "legal_agent": LegalAgent,
    "tax_agent": TaxAgent,
    "document_writer": DocumentWriterAgent,
    "orchestrator": OrchestratorAgent,
    "operator": OperatorAgent,
    "it_systems": ITSystemsAgent,
    "validation_engineer": ValidationEngineerAgent,
}
