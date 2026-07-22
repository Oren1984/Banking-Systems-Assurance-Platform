from __future__ import annotations

from scanners.file_classifier import classify_file, looks_sensitive_by_name


def test_classifies_python_source():
    result = classify_file("app/main.py", ".py")
    assert result.language == "python"
    assert result.detected_type == "source_code"
    assert result.category_flags["is_programming_language"] is True


def test_classifies_dockerfile():
    result = classify_file("Dockerfile", "")
    assert result.detected_type == "dockerfile"


def test_classifies_docker_compose():
    result = classify_file("docker-compose.yml", ".yml")
    assert result.detected_type == "docker_compose"


def test_classifies_terraform():
    result = classify_file("infra/main.tf", ".tf")
    assert result.detected_type == "terraform"
    assert result.category_flags["is_infrastructure_as_code"] is True


def test_classifies_sql_migration():
    result = classify_file("db/migrations/0001_init.sql", ".sql")
    assert result.detected_type == "sql"
    assert result.category_flags["database_schema_or_migration"] is True


def test_classifies_payment_related_by_path():
    result = classify_file("app/payments/processor.py", ".py")
    assert result.category_flags["payment_related"] is True


def test_classifies_customer_identity_related_by_path():
    result = classify_file("app/identity/onboarding.py", ".py")
    assert result.category_flags["customer_identity_related"] is True


def test_unrelated_file_has_no_domain_flags_set():
    result = classify_file("README.md", ".md")
    assert result.detected_type == "documentation"
    assert not any(
        v for k, v in result.category_flags.items() if k not in ("is_programming_language", "is_configuration")
    )


def test_looks_sensitive_by_name_matches_secret_keyword():
    assert looks_sensitive_by_name("config/db_credentials.secrets") is True
    assert looks_sensitive_by_name("config/api_key.bin") is True


def test_looks_sensitive_by_name_false_for_ordinary_file():
    assert looks_sensitive_by_name("app/main.py") is False
