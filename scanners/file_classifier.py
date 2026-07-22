from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# Phase 2 — File and Technology Classification
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §4). Deterministic,
# pattern-based only — no external AI provider is used or required.
# Adapted in spirit from ai-project-control-tower/app/scanner/file_classifier.py
# (that file did not exist in the delivered repository; this is a net-new
# implementation built for the unified platform's own file set).

_LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".cs": "csharp",
    ".go": "go",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
}

_CONFIG_EXTENSIONS = frozenset({".json", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties"})
_IAC_HINTS = ("terraform", ".tf", "kubernetes", "k8s", "helm", "ansible", "cloudformation")
_DEPLOYMENT_HINTS = ("dockerfile", "docker-compose", ".github/workflows", "deployment", "deploy/", "ci/", "cd/")

_DOMAIN_HINT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "database_schema_or_migration": ("migration", "schema", "alembic", "flyway", "liquibase", "ddl"),
    "api_definition": ("openapi", "swagger", "api_spec", "routes", "endpoints", ".proto"),
    "auth_config": ("auth", "oauth", "oidc", "saml", "jwt", "login", "credential"),
    "logging_config": ("logging", "logger", "log4j", "logback"),
    "monitoring_config": ("prometheus", "grafana", "monitoring", "metrics", "alertmanager"),
    "audit_related": ("audit", "compliance_log", "activity_log"),
    "payment_related": ("payment", "settlement", "transfer", "wire", "ach", "swift", "card_processing"),
    "account_related": ("account", "ledger", "balance", "statement"),
    "credit_lending_related": ("credit", "loan", "lending", "underwriting", "collections"),
    "investment_related": ("investment", "portfolio", "trading", "trade", "brokerage", "securities"),
    "customer_identity_related": ("customer", "kyc", "identity", "onboarding", "profile"),
    "data_governance_related": ("retention", "classification", "governance", "data_policy"),
    "security_controls": ("security", "iam", "rbac", "acl", "permission", "encryption", "tls"),
}


@dataclass
class ClassificationResult:
    language: str | None
    detected_type: str
    category_flags: dict[str, bool] = field(default_factory=dict)


def classify_file(relative_path: str, extension: str) -> ClassificationResult:
    """
    Classify a discovered file using only its path, name, and extension —
    no content is read here (content-based scanner rules live in
    scanners/rules/*.py and run separately, on already-read text).
    """
    path_lower = relative_path.lower()
    name_lower = PurePosixPath(relative_path).name.lower()
    ext = extension.lower()

    language = _LANGUAGE_BY_EXTENSION.get(ext)

    detected_type = _detect_type(path_lower, name_lower, ext)

    flags: dict[str, bool] = {
        "is_programming_language": language is not None,
        "is_configuration": ext in _CONFIG_EXTENSIONS,
        "is_infrastructure_as_code": any(h in path_lower for h in _IAC_HINTS) or ext == ".tf",
        "is_deployment_or_environment": any(h in path_lower for h in _DEPLOYMENT_HINTS) or name_lower == "dockerfile",
    }
    for flag_name, keywords in _DOMAIN_HINT_KEYWORDS.items():
        flags[flag_name] = any(kw in path_lower for kw in keywords)

    return ClassificationResult(language=language, detected_type=detected_type, category_flags=flags)


def _detect_type(path_lower: str, name_lower: str, ext: str) -> str:
    if name_lower in ("dockerfile",) or name_lower.startswith("dockerfile."):
        return "dockerfile"
    if "docker-compose" in name_lower:
        return "docker_compose"
    if ext == ".tf" or ext == ".tfvars":
        return "terraform"
    if ext == ".sql":
        return "sql"
    if ext in (".yaml", ".yml") and any(h in path_lower for h in (".github/workflows",)):
        return "ci_workflow"
    if ext in _CONFIG_EXTENSIONS:
        return "configuration"
    if ext in _LANGUAGE_BY_EXTENSION:
        return "source_code"
    if ext == ".md":
        return "documentation"
    if ext == ".csv":
        return "data_file"
    return "text"


_SECRET_LIKE_NAME = re.compile(r"(secret|credential|password|key|token)", re.IGNORECASE)


def looks_sensitive_by_name(relative_path: str) -> bool:
    """Cheap name-only heuristic used by scanners/rules/unsupported_file_scanner.py
    to flag unsupported files that are worth a human's attention even though
    their content was never read."""
    return bool(_SECRET_LIKE_NAME.search(relative_path))
