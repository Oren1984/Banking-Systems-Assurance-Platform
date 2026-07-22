from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VectorBackend = Literal["pgvector", "chroma"]
Environment = Literal["local", "dev", "staging", "prod"]

# Credential fragments that must never appear in a real database_url. This
# guards against accidentally copying ai-project-control-tower's insecure
# default (`postgresql://control_tower:control_tower_pass@...`, see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §10 finding #4) into the new platform.
_FORBIDDEN_CREDENTIAL_FRAGMENTS = ("control_tower_pass",)


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
    allowed_scan_paths: list[str] = Field(default_factory=list)
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


def get_settings() -> Settings:
    """Construct Settings fresh from the current environment (no caching)."""
    return Settings()
