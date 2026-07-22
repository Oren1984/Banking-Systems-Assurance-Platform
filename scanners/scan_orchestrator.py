from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.config import Settings
from core.exceptions import ScanError
from core.logging import get_logger
from models.enums import ScanStatus
from scanners.content_reader import BinaryContentError, read_text_safely
from scanners.domain_mapper import DomainMapping, map_file_to_domains
from scanners.file_classifier import classify_file
from scanners.file_discovery import compute_source_integrity_hash, discover_files
from scanners.rules.base import RawFinding
from scanners.rules.registry import get_content_scanners
from scanners.rules.unsupported_file_scanner import scan_skipped_files
from scanners.source_ingestion import SourceHandle

logger = get_logger(__name__)

# Phase 2 — Scan Orchestration (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 2 brief, §8). Synchronous, in-process — no async infrastructure,
# per the brief's own instruction ("a synchronous local scan with visible
# progress is acceptable for Phase 2"). Persistence (storage/db/repositories.py)
# is optional and separate: this module can run and be fully tested with
# no database at all.


@dataclass
class NormalizedFinding:
    """A RawFinding plus the scan/file context needed to persist it —
    the exact split file_discovery.py already established between
    in-memory pipeline objects and their persisted counterparts."""

    scan_id: str
    source_relative_path: str
    banking_domains: list[str]
    scanner_id: str
    scanner_version: str
    raw: RawFinding


@dataclass
class ScannerExecutionSummary:
    scanner_id: str
    scanner_version: str
    status: str  # "completed" | "completed_with_errors"
    files_processed: int
    files_errored: int
    findings_produced: int
    error_summary: Optional[str] = None


@dataclass
class ScanSummary:
    scan_id: str
    status: ScanStatus
    source_path: str
    source_type: str
    total_files_found: int
    files_scanned: int
    files_skipped: int
    total_findings: int
    truncated: bool
    integrity_verified: bool
    source_hash_before: str
    source_hash_after: str
    findings_by_severity: dict
    findings_by_domain: dict
    scanner_warnings: list
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]


@dataclass
class ScanResult:
    summary: ScanSummary
    inventory: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    domain_mappings: dict = field(default_factory=dict)  # relative_path -> list[DomainMapping]
    findings: list = field(default_factory=list)  # list[NormalizedFinding]
    scanner_executions: list = field(default_factory=list)  # list[ScannerExecutionSummary]


def run_scan(source: SourceHandle, settings: Settings) -> ScanResult:
    """
    Run one full Phase 2 read-only scan against an already-validated
    SourceHandle. Never raises for per-file or per-scanner failures — those
    are recorded and the scan completes as `completed_with_warnings`.
    Only raises ScanError for a failure that prevents the scan from
    running at all (e.g. the source integrity hash cannot be computed).
    """
    scan_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    warnings: list[str] = []

    logger.info("scan_started", scan_id=scan_id, source_type=source.source_type)

    try:
        hash_before = compute_source_integrity_hash(source.root)
    except Exception as exc:
        raise ScanError(f"Could not compute pre-scan integrity hash: {exc}") from exc

    try:
        discovery = discover_files(source.root, settings)
    except Exception as exc:
        raise ScanError(f"File discovery failed: {exc}") from exc

    domain_mappings: dict[str, list[DomainMapping]] = {}
    for item in discovery.inventory:
        classification = classify_file(item.relative_path, item.extension)
        domain_mappings[item.relative_path] = map_file_to_domains(item.relative_path, classification)
        item.metadata["detected_type"] = classification.detected_type
        item.metadata["language"] = classification.language
        item.metadata["sensitivity_hint"] = _looks_sensitive(classification)

    findings: list[NormalizedFinding] = []
    executions: list[ScannerExecutionSummary] = []

    for scanner in get_content_scanners():
        summary = _run_one_scanner(scanner, discovery.inventory, source, settings, scan_id, domain_mappings, findings)
        executions.append(summary)
        if summary.status == "completed_with_errors":
            warnings.append(f"{scanner.scanner_id}: {summary.files_errored} file(s) could not be scanned")

    skip_findings = scan_skipped_files(discovery.skipped)
    for raw in skip_findings:
        findings.append(
            NormalizedFinding(
                scan_id=scan_id,
                source_relative_path=raw.evidence,
                banking_domains=[],
                scanner_id="unsupported_sensitive_file",
                scanner_version="1.0.0",
                raw=raw,
            )
        )
    executions.append(
        ScannerExecutionSummary(
            scanner_id="unsupported_sensitive_file",
            scanner_version="1.0.0",
            status="completed",
            files_processed=len(discovery.skipped),
            files_errored=0,
            findings_produced=len(skip_findings),
        )
    )

    findings = _deduplicate(findings)

    try:
        hash_after = compute_source_integrity_hash(source.root)
    except Exception as exc:
        raise ScanError(f"Could not compute post-scan integrity hash: {exc}") from exc

    integrity_verified = hash_before == hash_after
    if not integrity_verified:
        # This must never happen for a correctly-implemented read-only
        # scan. Surface it loudly rather than silently marking the scan
        # successful — a failed integrity check is itself the most
        # important finding this platform can produce.
        warnings.append("SOURCE INTEGRITY CHECK FAILED — source hash changed during scan")
        logger.error("scan_integrity_check_failed", scan_id=scan_id)

    any_scanner_errors = any(e.status == "completed_with_errors" for e in executions)
    status = ScanStatus.COMPLETED
    if not integrity_verified:
        status = ScanStatus.FAILED
    elif any_scanner_errors or discovery.truncated:
        status = ScanStatus.COMPLETED_WITH_WARNINGS

    completed_at = datetime.now(timezone.utc)

    summary = ScanSummary(
        scan_id=scan_id,
        status=status,
        source_path=str(source.original_path),
        source_type=source.source_type,
        total_files_found=discovery.total_files_found,
        files_scanned=len(discovery.inventory),
        files_skipped=len(discovery.skipped),
        total_findings=len(findings),
        truncated=discovery.truncated,
        integrity_verified=integrity_verified,
        source_hash_before=hash_before,
        source_hash_after=hash_after,
        findings_by_severity=_count_by(findings, lambda f: f.raw.severity.value),
        findings_by_domain=_count_by_domain(findings),
        scanner_warnings=warnings,
        error_message=None if integrity_verified else "Source integrity check failed",
        started_at=started_at,
        completed_at=completed_at,
    )

    logger.info(
        "scan_completed",
        scan_id=scan_id,
        status=status.value,
        total_findings=len(findings),
        integrity_verified=integrity_verified,
    )

    return ScanResult(
        summary=summary,
        inventory=discovery.inventory,
        skipped=discovery.skipped,
        domain_mappings=domain_mappings,
        findings=findings,
        scanner_executions=executions,
    )


def _run_one_scanner(
    scanner,
    inventory: list,
    source: SourceHandle,
    settings: Settings,
    scan_id: str,
    domain_mappings: dict,
    findings_out: list,
) -> ScannerExecutionSummary:
    processed = 0
    errored = 0
    produced = 0
    error_details: list[str] = []

    for item in inventory:
        file_path = source.root / item.relative_path
        try:
            read_result = read_text_safely(file_path, settings)
        except BinaryContentError:
            continue
        except OSError as exc:
            errored += 1
            error_details.append(f"{item.relative_path}: unreadable")
            logger.warning("scan_file_read_failed", scanner_id=scanner.scanner_id, error=type(exc).__name__)
            continue

        try:
            raw_findings = scanner.scan(item.relative_path, read_result.text)
        except Exception as exc:  # noqa: BLE001 — one scanner failing must not fail the scan
            errored += 1
            error_details.append(f"{item.relative_path}: scanner error ({type(exc).__name__})")
            logger.warning("scanner_rule_failed", scanner_id=scanner.scanner_id, error=type(exc).__name__)
            continue

        processed += 1
        domains = [m.domain.value for m in domain_mappings.get(item.relative_path, [])]
        for raw in raw_findings:
            findings_out.append(
                NormalizedFinding(
                    scan_id=scan_id,
                    source_relative_path=item.relative_path,
                    banking_domains=domains,
                    scanner_id=scanner.scanner_id,
                    scanner_version=scanner.scanner_version,
                    raw=raw,
                )
            )
            produced += 1

    status = "completed_with_errors" if errored else "completed"
    return ScannerExecutionSummary(
        scanner_id=scanner.scanner_id,
        scanner_version=scanner.scanner_version,
        status=status,
        files_processed=processed,
        files_errored=errored,
        findings_produced=produced,
        error_summary="; ".join(error_details[:10]) if error_details else None,
    )


def _deduplicate(findings: list) -> list:
    """Drop exact duplicates: same rule, same file, same line, same
    scanner — can legitimately happen if two supported-extension checks
    both match the same file (e.g. a .env file classified two ways)."""
    seen: set[tuple] = set()
    out = []
    for f in findings:
        key = (f.raw.rule_id, f.source_relative_path, f.raw.line_start, f.raw.line_end)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _looks_sensitive(classification) -> bool:
    return bool(
        classification.category_flags.get("payment_related")
        or classification.category_flags.get("customer_identity_related")
        or classification.category_flags.get("auth_config")
        or classification.category_flags.get("account_related")
    )


def _count_by(findings: list, key_fn) -> dict:
    counts: dict = {}
    for f in findings:
        k = key_fn(f)
        counts[k] = counts.get(k, 0) + 1
    return counts


def _count_by_domain(findings: list) -> dict:
    counts: dict = {}
    for f in findings:
        for domain in f.banking_domains:
            counts[domain] = counts.get(domain, 0) + 1
    return counts
