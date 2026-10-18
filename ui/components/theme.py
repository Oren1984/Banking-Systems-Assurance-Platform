from __future__ import annotations

import streamlit as st

# One small stylesheet on top of .streamlit/config.toml's theme. Uses
# Streamlit's own theme variables where possible and translucent colours
# otherwise, so the same rules read correctly in light and dark mode.
# Nothing here is required for function — it only tightens spacing and
# gives bordered containers a card look.

_CSS = """
<style>
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
[data-testid="stMetric"] {
    background: rgba(31, 78, 121, 0.05);
    border: 1px solid rgba(31, 78, 121, 0.14);
    border-radius: 12px;
    padding: 0.75rem 1rem;
}
[data-testid="stMetricLabel"] p { font-size: 0.82rem; opacity: 0.8; }
[data-testid="stMetricValue"] { font-size: 1.7rem; }
[data-testid="stSidebarNav"] { padding-top: 0.5rem; }
.bsap-brand { font-weight: 700; font-size: 1.05rem; letter-spacing: 0.01em; }
.bsap-muted { opacity: 0.7; font-size: 0.85rem; }
.bsap-login-title { text-align: center; margin-bottom: 0.25rem; }
.bsap-login-sub { text-align: center; opacity: 0.75; margin-bottom: 1.25rem; }
.bsap-footer { text-align: center; opacity: 0.7; font-size: 0.8rem; margin-top: 2rem; }
@media (max-width: 640px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>
"""


def apply_theme() -> None:
    st.html(_CSS)
