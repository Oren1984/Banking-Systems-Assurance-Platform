from __future__ import annotations


class PlatformError(Exception):
    """Base exception for all Banking Systems Assurance Platform errors."""


class ConfigurationError(PlatformError):
    """Raised when configuration is missing, invalid, or incompatible."""


class ValidationError(PlatformError):
    """Raised when input fails validation (files, queries, parameters, paths)."""


class PathValidationError(PlatformError):
    """Raised when a requested scan/document path fails allowlist validation."""


class IngestionError(PlatformError):
    """Raised when document loading or parsing fails."""


class ChunkingError(PlatformError):
    """Raised when text chunking fails."""


class EmbeddingError(PlatformError):
    """Raised when embedding generation fails (e.g. API error, model load failure)."""


class VectorStoreError(PlatformError):
    """Raised when a vector store operation fails (add, search, delete, clear)."""


class RetrievalError(PlatformError):
    """Raised when the retrieval pipeline fails."""


class ProviderError(PlatformError):
    """Base exception for optional external AI provider errors."""


class ProviderDisabledError(ProviderError):
    """Raised when a provider adapter is invoked while disabled by configuration."""


class AssessmentError(PlatformError):
    """Raised when the assessment/scoring pipeline fails."""


class GovernanceError(PlatformError):
    """Raised when a governance/sanitization control cannot be satisfied."""


class SourceIngestionError(IngestionError):
    """Raised when a scan source (directory or archive) cannot be safely
    accepted — includes Zip Slip / path-traversal / archive-bomb rejection
    (scanners/source_ingestion.py)."""


class ScanError(PlatformError):
    """Raised when the scan orchestration pipeline fails
    (scanners/scan_orchestrator.py)."""
