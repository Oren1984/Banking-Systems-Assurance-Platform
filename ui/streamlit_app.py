from __future__ import annotations

from ui.shell import run_app

# Legacy entrypoint, kept so existing run commands keep working:
#     streamlit run ui/streamlit_app.py
#
# It now runs exactly the same authenticated, role-based application as
# ui/app.py — the same sign-in gate, the same permission checks, the same
# secured service layer. There is no unauthenticated mode left behind this
# path.
#
# The previous single-page, unauthenticated UI (Phase 2 Quick Scan + Phase 5
# Full Assessment + Phase 6 AI Assistant tabs, with self-typed reviewer
# names) was retired once the multipage UI reached feature parity; see
# docs/ui_feature_parity.md for the capability-by-capability mapping. Its
# source remains in git history (commit 15cfd06 and earlier).

run_app()
