from __future__ import annotations

import streamlit as st

from core.config import get_settings
from core.domains import get_domain_label
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory, ingest_zip_archive
from reporting.scan_report_exporter import to_json, to_markdown

# Phase 2 — Minimal Streamlit Workflow (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 2 brief, §10). Deliberately a single file, calling
# scanners.scan_orchestrator directly and synchronously — no FastAPI route
# layer, no async infrastructure, per the brief's own instruction to avoid
# overengineering for Phase 2. This is not the final production UI (see
# ui/README.md for what Phase 6 will build instead).

st.set_page_config(page_title="Banking Systems Assurance Platform — Scan", layout="wide")


def _status_banner(settings) -> None:
    cols = st.columns(4)
    cols[0].metric("Mode", "READ-ONLY")
    cols[1].metric("Local-only", "YES" if settings.local_only_mode else "NO")
    cols[2].metric("External providers", "DISABLED" if not settings.external_providers_enabled else "ENABLED")
    cols[3].metric("Vector backend", settings.vector_backend)


def main() -> None:
    settings = get_settings()

    st.title("Banking Systems Assurance Platform")
    st.caption("Phase 2 — local read-only ingestion and scanning (not the final production UI)")
    _status_banner(settings)

    st.divider()
    st.header("1. Select Local Source")

    source_kind = st.radio("Source type", ["Local directory", "ZIP archive"], horizontal=True)
    source_path = st.text_input(
        "Path (must be inside an ALLOWED_SCAN_PATHS entry)",
        placeholder=r"C:\path\to\project or C:\path\to\archive.zip",
    )

    if "scan_result" not in st.session_state:
        st.session_state["scan_result"] = None

    if st.button("Validate and Start Read-Only Scan", type="primary", disabled=not source_path):
        _run(source_kind, source_path, settings)

    result = st.session_state["scan_result"]
    if result is None:
        return

    st.divider()
    st.header("2. Scan Summary")
    summary = result.summary
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", summary.status.value)
    c2.metric("Files discovered", summary.total_files_found)
    c3.metric("Files scanned", summary.files_scanned)
    c4.metric("Files skipped", summary.files_skipped)

    c5, c6 = st.columns(2)
    c5.metric("Total findings", summary.total_findings)
    c6.metric("Source integrity verified", "YES" if summary.integrity_verified else "NO — SEE WARNINGS")

    if summary.scanner_warnings:
        for w in summary.scanner_warnings:
            st.warning(w)

    st.subheader("Findings by severity")
    st.bar_chart(summary.findings_by_severity)

    st.subheader("Findings by banking domain")
    if summary.findings_by_domain:
        labeled = {
            get_domain_label_safe(domain): count for domain, count in summary.findings_by_domain.items()
        }
        st.bar_chart(labeled)
    else:
        st.write("No findings were mapped to a banking domain in this scan.")

    st.divider()
    st.header("3. Findings")

    all_severities = sorted({f.raw.severity.value for f in result.findings})
    all_domains = sorted({d for f in result.findings for d in f.banking_domains})
    all_categories = sorted({f.raw.category.value for f in result.findings})
    all_scanners = sorted({f.scanner_id for f in result.findings})

    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    severity_filter = fc1.multiselect("Severity", all_severities)
    domain_filter = fc2.multiselect("Banking domain", all_domains)
    category_filter = fc3.multiselect("Category", all_categories)
    path_filter = fc4.text_input("File path contains")
    scanner_filter = fc5.multiselect("Scanner", all_scanners)

    filtered = _filter_findings(result.findings, severity_filter, domain_filter, category_filter, path_filter, scanner_filter)

    st.write(f"Showing {len(filtered)} of {len(result.findings)} findings")
    for normalized in filtered:
        raw = normalized.raw
        with st.expander(f"[{raw.severity.value.upper()}] {raw.title} — {normalized.source_relative_path}:{raw.line_start}"):
            st.write(f"**Category:** {raw.category.value}  |  **Confidence:** {raw.confidence.value}  |  **Type:** {raw.finding_type.value}")
            st.write(f"**Banking domains:** {', '.join(normalized.banking_domains) or 'none mapped'}")
            st.code(raw.masked_evidence)
            st.write(f"**Description:** {raw.description}")
            st.write(f"**Impact:** {raw.impact}")
            st.write(f"**Recommended action (advisory only — never auto-applied):** {raw.recommended_action}")

    st.divider()
    st.header("4. Export Report")
    ec1, ec2 = st.columns(2)
    ec1.download_button("Download JSON", to_json(result), file_name=f"scan_{summary.scan_id}.json", mime="application/json")
    ec2.download_button("Download Markdown", to_markdown(result), file_name=f"scan_{summary.scan_id}.md", mime="text/markdown")


def _run(source_kind: str, source_path: str, settings) -> None:
    with st.spinner("Validating source and running read-only scan..."):
        try:
            if source_kind == "ZIP archive":
                source = ingest_zip_archive(source_path, settings)
            else:
                source = ingest_local_directory(source_path, settings)
            try:
                result = run_scan(source, settings)
            finally:
                source.cleanup()
            st.session_state["scan_result"] = result
        except Exception as exc:  # noqa: BLE001 — surface any ingestion/scan error to the operator, not a crash
            st.session_state["scan_result"] = None
            st.error(f"Scan could not be completed: {exc}")


def get_domain_label_safe(domain_value: str) -> str:
    from core.domains import BankingDomain

    try:
        return get_domain_label(BankingDomain(domain_value))
    except ValueError:
        return domain_value


def _filter_findings(findings, severities, domains, categories, path_substring, scanners):
    out = []
    for f in findings:
        if severities and f.raw.severity.value not in severities:
            continue
        if domains and not (set(f.banking_domains) & set(domains)):
            continue
        if categories and f.raw.category.value not in categories:
            continue
        if path_substring and path_substring.lower() not in f.source_relative_path.lower():
            continue
        if scanners and f.scanner_id not in scanners:
            continue
        out.append(f)
    return out


if __name__ == "__main__":
    main()
