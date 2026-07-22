from __future__ import annotations

import importlib

import pytest

# BANKING_PLATFORM_INTEGRATION_PLAN.md Part C §11: "local imports/startup
# do not require OpenAI, Gemini, or Anthropic SDKs". None of these packages
# are installed in this environment (see PHASE_1_COMPLETION_REPORT.md), so
# these imports succeeding at all is itself evidence for the requirement —
# if any Phase 1 module had a hard top-level dependency on one of those
# SDKs, these imports would fail with ModuleNotFoundError.

_CORE_MODULES = [
    "core.config",
    "core.contracts",
    "core.domains",
    "core.exceptions",
    "core.logging",
    "governance.secret_masker",
    "governance.report_sanitizer",
    "governance.pii_redaction",
    "governance.prompt_safety",
    "governance.file_validation",
    "scanners.path_validator",
    "rag.embeddings.mock_embedding_provider",
    "rag.vectorstores.chroma_store",
    "rag.vectorstores.pgvector_store",
    "rag.vectorstores.registry",
    "providers.base",
    "providers.registry",
    "providers.openai_adapter",
    "providers.gemini_adapter",
    "providers.claude_adapter",
    "storage.db.base",
    "storage.db.session",
    "storage.db.models",
    "storage.db.repositories",
    "app.main",
    # Phase 2
    "scanners.source_ingestion",
    "scanners.file_discovery",
    "scanners.content_reader",
    "scanners.file_classifier",
    "scanners.domain_mapper",
    "scanners.scan_orchestrator",
    "scanners.rules.base",
    "scanners.rules.registry",
    "scanners.rules.secret_scanner",
    "scanners.rules.pii_scanner",
    "scanners.rules.unsafe_logging_scanner",
    "scanners.rules.audit_scanner",
    "scanners.rules.permission_scanner",
    "scanners.rules.sql_scanner",
    "scanners.rules.insecure_config_scanner",
    "scanners.rules.unsupported_file_scanner",
    "reporting.scan_report_exporter",
]


@pytest.mark.parametrize("module_name", _CORE_MODULES)
def test_module_imports_without_provider_sdks(module_name):
    importlib.import_module(module_name)


def test_provider_sdks_are_not_installed_in_this_environment():
    for sdk in ("openai", "google.generativeai", "anthropic"):
        with pytest.raises(ImportError):
            importlib.import_module(sdk)
