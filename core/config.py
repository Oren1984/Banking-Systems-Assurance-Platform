from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

VectorBackend = Literal["pgvector", "chroma"]
Environment = Literal["local", "dev", "staging", "prod"]

# Credential fragments that must never appear in a real database_url. This
# guards against accidentally copying ai-project-control-tower's insecure
# default (`postgresql://control_tower:control_tower_pass@...`, see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §10 finding #4) into the new platform.
_FORBIDDEN_CREDENTIAL_FRAGMENTS = ("control_tower_pass",)
_DEFAULT_MOCK_BANKING_SYSTEM_PATH = "mock_banking_system"
_DEFAULT_REFERENCE_BANKING_SYSTEM_PATH = "reference_banking_system"


class Settings(BaseSettings):
    """
    Unified, typed configuration for the Banking Systems Assurance Platform.

    Local-first and read-only-safe by construction:
    - LOCAL_ONLY_MODE and EXTERNAL_PROVIDERS_ENABLED both default to safe values.
    - No field carries a live or placeholder credential as a default.
    - VECTOR_BACKEND is a closed Literal, so an invalid value fails at
      construction time with a clear pydantic ValidationError.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---------------------------------------------------
    app_name: str = "Banking Systems Assurance Platform"
    app_version: str = "0.1.0"
    environment: Environment = "local"
    debug: bool = False
    log_level: str = "INFO"

    # --- Local-first / external-provider kill switches ------------------
    # LOCAL_ONLY_MODE and EXTERNAL_PROVIDERS_ENABLED are intentionally
    # separate flags: local_only_mode documents platform intent, while
    # external_providers_enabled is the hard kill switch actually checked
    # by providers/registry.py before constructing any adapter.
    local_only_mode: bool = True
    external_providers_enabled: bool = False

    openai_enabled: bool = False
    gemini_enabled: bool = False
    claude_enabled: bool = False

    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None

    # --- Vector backend ---------------------------------------------------
    # pgvector is the approved primary persistent backend; chroma is the
    # approved secondary portable/local backend. No other value is valid.
    vector_backend: VectorBackend = "pgvector"
    chroma_persist_directory: str = "data/chroma"
    chroma_collection_name: str = "banking_assurance_chunks"

    # --- PostgreSQL / pgvector ----------------------------------------------
    # No default value, and never a placeholder credential: a banking
    # platform must not ship with any embedded database password, not even
    # a fake one. Must be set explicitly via DATABASE_URL for any real run.
    database_url: Optional[str] = None

    # --- Local embeddings ----------------------------------------------------
    embedding_provider: str = "local"

    # --- Scanning boundary (fail-closed if empty; see scanners/path_validator.py)
    # `NoDecode` is required here: pydantic-settings' env source otherwise
    # attempts to JSON-decode any non-scalar-typed field read from an
    # environment variable *before* this model's own `_parse_scan_paths`
    # validator ever runs — a plain comma-separated string (the format
    # .env.example documents and _parse_scan_paths is written to accept)
    # is not valid JSON, so without NoDecode, setting ALLOWED_SCAN_PATHS as
    # an actual environment variable crashes with a SettingsError before
    # construction completes. Found running the Phase 5 demo UI against a
    # real environment variable, not merely a constructor kwarg (every
    # existing test constructed Settings with allowed_scan_paths= directly,
    # which bypasses the env source entirely and never exercised this
    # path) — see PHASE_5_COMPLETION_REPORT.md.
    allowed_scan_paths: Annotated[list[str], NoDecode] = Field(default_factory=list)
    max_scan_file_size_bytes: int = 1_048_576  # 1 MB, per file
    max_scan_total_size_bytes: int = 209_715_200  # 200 MB, whole scan
    max_scan_file_count: int = 20_000
    max_scan_depth: int = 40
    scan_follow_symlinks: bool = False  # symlinks are skipped by default

    # --- Archive (zip) ingestion safety (scanners/source_ingestion.py) --------
    max_archive_entry_count: int = 20_000
    max_archive_uncompressed_bytes: int = 209_715_200  # 200 MB, matches max_scan_total_size_bytes
    max_archive_compression_ratio: int = 100  # reject entries expanding >100x (zip-bomb heuristic)
    scan_temp_dir: str = "data/scan_tmp"  # isolated extraction root, cleaned up after use

    # --- Storage paths -----------------------------------------------------
    document_storage_dir: str = "data/documents"
    report_output_dir: str = "data/reports"

    # --- Retention foundations (governance/retention.py) --------------------
    # None = retention identification disabled by default; a platform
    # operator must explicitly opt in. See governance/retention.py's module
    # docstring for what this does and, just as importantly, does not do.
    data_retention_days: Optional[int] = Field(default=None, ge=0)

    # --- Optional external-agent boundary (agents/, Phase 6) -----------------
    # AGENT_ENABLED is a separate, higher-level switch from
    # EXTERNAL_PROVIDERS_ENABLED: an operator can enable the agent *feature*
    # (agents/registry.py will still only ever hand back the deterministic
    # local mode, never silently reach for openai/gemini/claude) without
    # also opting into real external transmission. Both this flag AND
    # agent_provider != "local" AND external_providers_enabled AND the
    # specific provider's own enable flag/API key must all hold before
    # agents/registry.py::get_agent_provider() returns anything external —
    # see that module's own docstring for the exact precedence.
    agent_enabled: bool = False
    agent_provider: Literal["local", "openai", "gemini", "claude"] = "local"
    agent_model_name: Optional[str] = None
    agent_timeout_seconds: float = 30.0
    agent_max_retries: int = 1
    # Hard cap on sanitized context sent to any provider (local or
    # external) — enforced by agents/sanitizer.py, independent of whatever
    # limit a specific provider's own API might additionally impose.
    agent_max_context_chars: int = 4000
    # Hard cap on how many findings/evidence snippets one agent context may
    # include — prevents a "summarize everything" request from silently
    # growing into a near-full-repository payload.
    agent_max_evidence_items: int = 5

    @field_validator("database_url")
    @classmethod
    def _reject_known_insecure_defaults(cls, v: Optional[str]) -> Optional[str]:
        if v:
            for fragment in _FORBIDDEN_CREDENTIAL_FRAGMENTS:
                if fragment in v:
                    raise ValueError(
                        f"database_url contains a known insecure placeholder "
                        f"credential fragment ({fragment!r}); set an explicit, "
                        f"real credential instead."
                    )
        return v

    @field_validator("allowed_scan_paths", mode="before")
    @classmethod
    def _parse_scan_paths(cls, v: object) -> list[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return []

    @property
    def mock_banking_system_path(self) -> str:
        """Return the configured source path for the built-in mock demo."""
        for allowed_path in self.allowed_scan_paths:
            normalized = allowed_path.replace("\\", "/").rstrip("/")
            if normalized.endswith("/mock_banking_system") or normalized == _DEFAULT_MOCK_BANKING_SYSTEM_PATH:
                return allowed_path.rstrip("\\/")
            if normalized.endswith("/scan-targets") or normalized == "/scan-targets":
                return f"{normalized}/mock_banking_system"

            candidate = Path(allowed_path) / "mock_banking_system"
            if candidate.exists():
                return str(candidate)

        return _DEFAULT_MOCK_BANKING_SYSTEM_PATH

    @property
    def reference_banking_system_path(self) -> str:
        """Return the configured source path for the built-in, well-governed
        reference demo (a second, additive fixture — see
        reference_banking_system/README.md). Mirrors mock_banking_system_path's
        resolution logic exactly, for the same reasons."""
        for allowed_path in self.allowed_scan_paths:
            normalized = allowed_path.replace("\\", "/").rstrip("/")
            if normalized.endswith("/reference_banking_system") or normalized == _DEFAULT_REFERENCE_BANKING_SYSTEM_PATH:
                return allowed_path.rstrip("\\/")
            if normalized.endswith("/scan-targets") or normalized == "/scan-targets":
                return f"{normalized}/reference_banking_system"

            candidate = Path(allowed_path) / "reference_banking_system"
            if candidate.exists():
                return str(candidate)

        return _DEFAULT_REFERENCE_BANKING_SYSTEM_PATH


def get_settings() -> Settings:
    """Construct Settings fresh from the current environment (no caching)."""
    return Settings()
