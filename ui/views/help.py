from __future__ import annotations

import streamlit as st

from ui.app_context import page_setup
from ui.components.layout import page_title

# In-app Help / System Information (successor of the legacy sidebar panel).
# Summarizes README.md and docs/SECURITY.md; those files are
# authoritative if the two ever differ.

ctx, principal = page_setup(None)
page_title("Help & About", "What this platform is, how to use it, and its boundaries.")

st.markdown(
    "**What this is**  \n"
    "A read-only assessment and governance tool for banking-adjacent codebases. It scans an approved local "
    "source, maps findings to banking-domain controls, scores risk, and supports human governance review. "
    "**It is not a banking transaction system** and holds no customer accounts, balances, or payments.\n\n"
    "**Primary workflow**  \n"
    "Run & History → run a Full Assessment (ingest → scan → score → control evaluation) → Dashboard / Findings "
    "/ Controls → a Manager reviews findings and, with a justification, overrides scores in the Review Queue → "
    "Reports exports a sanitized report → Compare shows what changed since the previous run.\n\n"
    "**Roles**  \n"
    "- **Employee** — run Quick Scans and Full Assessments, view all assessment information, use the AI Assistant.\n"
    "- **Manager** — everything an Employee can do, plus review findings, override scores, export reports, view the audit log.\n"
    "- **Admin** — manage user accounts, view all information, export reports, view the audit log and system "
    "information. Admins deliberately **cannot** review findings or override scores (separation of duties).\n\n"
    "**Security and privacy boundaries (implemented)**  \n"
    "- Scanning is strictly read-only; source-integrity hashing verifies nothing was modified.\n"
    "- Sign-in is required; passwords are stored only as salted scrypt hashes. Accounts lock for 15 minutes "
    "after 5 failed attempts; idle sessions expire.\n"
    "- Every action is permission-checked on the server, and every reviewer/actor in the audit trail is the "
    "signed-in user. Denied actions are audited.\n"
    "- Secrets and PII in scan output are masked before storage and display (pattern-based, not exhaustive).\n"
    "- Recommendations are advisory only — the platform never remediates a scanned system.\n"
    "- The AI Assistant defaults to a local, non-network mode and can never make a governance decision.\n\n"
    "**Known limitations**  \n"
    "- No MFA or SSO; accounts are local to this platform.\n"
    "- Designed for local use: the app is bound to localhost and served over plain HTTP. **HTTPS must be configured "
    "before allowing access from any other computer or the internet.**\n"
    "- Refreshing the browser tab starts a new session (sign in again).\n"
    "- PII/secret detection is pattern-based and explicitly not exhaustive.\n"
    "- No production-grade monitoring/alerting stack.\n\n"
    "**This is a portfolio-grade POC/MVP.** It demonstrates an assurance workflow, not a production-ready or "
    "regulation-compliant system. See `README.md` and `docs/SECURITY.md`."
)
