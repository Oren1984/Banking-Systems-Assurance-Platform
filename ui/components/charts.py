from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable

import altair as alt
import pandas as pd
import streamlit as st

from ui.components.badges import DECISION_HEX, DECISION_ORDER, SEVERITY_HEX, SEVERITY_ORDER, domain_label, humanize

# Altair charts (bundled with Streamlit — no new dependency). Colours come
# from ui/components/badges.py so a severity or decision category looks the
# same in a chart as in a badge. Transparent backgrounds keep them readable
# in light and dark themes.


def _base(chart: alt.Chart, height: int) -> alt.Chart:
    return chart.properties(height=height).configure_view(strokeWidth=0).configure_axis(grid=False, labelLimit=260)


def domain_scores_chart(effective_scores: Dict[str, object]) -> None:
    rows = [
        {
            "Domain": domain_label(domain),
            "Weighted score": s.weighted_score if s.weighted_score is not None else 0.0,
            "Score": f"{s.weighted_score:.1f}" if s.weighted_score is not None else "n/a",
            "Decision": humanize(s.decision_category),
            "category": s.decision_category,
        }
        for domain, s in effective_scores.items()
    ]
    if not rows:
        st.caption("No domain scores recorded.")
        return
    df = pd.DataFrame(rows).sort_values("Weighted score")
    present = [c for c in DECISION_ORDER if c in set(df["category"])]
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("Weighted score:Q", scale=alt.Scale(domain=[0, 100]), title="Weighted score (0–100)"),
            y=alt.Y("Domain:N", sort=None, title=None),
            color=alt.Color(
                "Decision:N",
                scale=alt.Scale(domain=[humanize(c) for c in present], range=[DECISION_HEX[c] for c in present]),
                legend=alt.Legend(orient="bottom", title=None, columns=3),
            ),
            tooltip=["Domain", "Score", "Decision"],
        )
    )
    st.altair_chart(_base(chart, max(220, 26 * len(df))), width="stretch")


def severity_chart(severities: Iterable[str]) -> None:
    counts = Counter(str(s).lower() for s in severities)
    if not counts:
        st.caption("No findings.")
        return
    order = [s for s in SEVERITY_ORDER if counts.get(s)] + sorted(set(counts) - set(SEVERITY_ORDER))
    df = pd.DataFrame({"Severity": [s.upper() for s in order], "Findings": [counts[s] for s in order]})
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("Findings:Q", title="Findings"),
            y=alt.Y("Severity:N", sort=[s.upper() for s in order], title=None),
            color=alt.Color(
                "Severity:N",
                scale=alt.Scale(domain=[s.upper() for s in order], range=[SEVERITY_HEX.get(s, "#7A8794") for s in order]),
                legend=None,
            ),
            tooltip=["Severity", "Findings"],
        )
    )
    st.altair_chart(_base(chart, 40 * len(order) + 40), width="stretch")


def count_chart(counts: Dict[str, int], label: str) -> None:
    if not counts:
        st.caption("Nothing to chart.")
        return
    df = pd.DataFrame({label: [humanize(k) for k in counts], "Count": list(counts.values())})
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, color="#1F4E79")
        .encode(x=alt.X("Count:Q"), y=alt.Y(f"{label}:N", sort="-x", title=None), tooltip=[label, "Count"])
    )
    st.altair_chart(_base(chart, 34 * len(df) + 40), width="stretch")
