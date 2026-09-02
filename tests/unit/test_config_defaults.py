from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config import Settings


def test_local_only_mode_defaults_true(monkeypatch):
    monkeypatch.delenv("LOCAL_ONLY_MODE", raising=False)
    s = Settings(_env_file=None)
    assert s.local_only_mode is True


def test_external_providers_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EXTERNAL_PROVIDERS_ENABLED", raising=False)
    s = Settings(_env_file=None)
    assert s.external_providers_enabled is False
    assert s.openai_enabled is False
    assert s.gemini_enabled is False
    assert s.claude_enabled is False


def test_no_api_keys_required_for_local_startup():
    s = Settings(_env_file=None)
    assert s.openai_api_key is None
    assert s.gemini_api_key is None
    assert s.claude_api_key is None


def test_vector_backend_defaults_to_pgvector():
    s = Settings(_env_file=None)
    assert s.vector_backend == "pgvector"


def test_vector_backend_accepts_chroma_via_env(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "chroma")
    s = Settings(_env_file=None)
    assert s.vector_backend == "chroma"


def test_vector_backend_accepts_chroma_via_direct_kwarg():
    s = Settings(_env_file=None, vector_backend="chroma")
    assert s.vector_backend == "chroma"


def test_invalid_vector_backend_fails_clearly_via_env(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "faiss")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_vector_backend_fails_clearly_via_kwarg():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vector_backend="faiss")


def test_no_default_database_credential():
    s = Settings(_env_file=None)
    assert s.database_url is None


def test_rejects_legacy_insecure_placeholder_credential():
    bad_url = (
        "postgresql://control_tower:control_tower_pass@localhost:5432/db"
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=bad_url)


def test_allowed_scan_paths_defaults_empty():
    s = Settings(_env_file=None)
    assert s.allowed_scan_paths == []


def test_allowed_scan_paths_parses_comma_separated():
    s = Settings(_env_file=None, allowed_scan_paths="/a,/b, /c")
    assert s.allowed_scan_paths == ["/a", "/b", "/c"]


def test_allowed_scan_paths_parses_a_real_environment_variable(monkeypatch):
    # Regression test (Phase 5): a plain-string ALLOWED_SCAN_PATHS env var
    # used to crash with pydantic_settings.SettingsError at construction —
    # pydantic-settings' env source tried to JSON-decode it before this
    # model's own comma-parsing validator ever ran. The two tests above
    # both construct Settings with allowed_scan_paths= as a direct kwarg,
    # which bypasses the env source entirely and never exercised this path.
    # Fixed via Annotated[list[str], NoDecode] on the field — see
    # core/config.py and docs/security_boundaries.md.
    monkeypatch.setenv("ALLOWED_SCAN_PATHS", "mock_banking_system,/tmp/other")
    s = Settings(_env_file=None)
    assert s.allowed_scan_paths == ["mock_banking_system", "/tmp/other"]


def test_mock_banking_system_path_uses_exact_allowlisted_fixture_path():
    s = Settings(_env_file=None, allowed_scan_paths=["/scan-targets/mock_banking_system"])
    assert s.mock_banking_system_path == "/scan-targets/mock_banking_system"


def test_mock_banking_system_path_discovers_fixture_under_allowed_repo_root(tmp_path):
    fixture = tmp_path / "mock_banking_system"
    fixture.mkdir()
    s = Settings(_env_file=None, allowed_scan_paths=[str(tmp_path)])
    assert s.mock_banking_system_path == str(fixture)


def test_reference_banking_system_path_uses_exact_allowlisted_fixture_path():
    s = Settings(_env_file=None, allowed_scan_paths=["/scan-targets/reference_banking_system"])
    assert s.reference_banking_system_path == "/scan-targets/reference_banking_system"


def test_reference_banking_system_path_discovers_fixture_under_allowed_repo_root(tmp_path):
    fixture = tmp_path / "reference_banking_system"
    fixture.mkdir()
    s = Settings(_env_file=None, allowed_scan_paths=[str(tmp_path)])
    assert s.reference_banking_system_path == str(fixture)
