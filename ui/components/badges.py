from __future__ import annotations

from core.domains import BankingDomain, get_domain_label

# Text badges rendered with Streamlit's built-in Markdown badge syntax
# (`:color-badge[text]`) — no raw HTML, so values can never inject markup.
# One colour vocabulary for the whole UI; charts reuse the same order.

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_COLORS = {"critical": "red", "high": "orange", "medium": "violet", "low": "blue", "info": "gray"}
SEVERITY_HEX = {"critical": "#C62828", "high": "#EF6C00", "medium": "#7B4FB8", "low": "#1E6FB8", "info": "#7A8794"}

DECISION_ORDER = [
    "critical_risk",
    "high_risk",
    "remediation_required",
    "manual_review_required",
    "insufficient_evidence",
    "acceptable_with_observations",
    "acceptable",
]
DECISION_COLORS = {
    "critical_risk": "red",
    "high_risk": "orange",
    "remediation_required": "violet",
    "manual_review_required": "blue",
    "insufficient_evidence": "gray",
    "acceptable_with_observations": "green",
    "acceptable": "green",
}
DECISION_HEX = {
    "critical_risk": "#C62828",
    "high_risk": "#EF6C00",
    "remediation_required": "#7B4FB8",
    "manual_review_required": "#1E6FB8",
    "insufficient_evidence": "#7A8794",
    "acceptable_with_observations": "#5E9E4B",
    "acceptable": "#2E7D32",
}
REVIEW_COLORS = {"pending": "orange", "approved": "green", "rejected": "gray", "overridden": "blue"}
ROLE_COLORS = {"admin": "red", "manager": "blue", "employee": "green"}


def _safe(text: str) -> str:
    # Square brackets would end the badge early.
    return str(text).replace("[", "(").replace("]", ")")


def badge(text: str, color: str) -> str:
    return f":{color}-badge[{_safe(text)}]"


def severity_badge(severity: str) -> str:
    return badge(str(severity).upper(), SEVERITY_COLORS.get(str(severity).lower(), "gray"))


def decision_badge(category: str) -> str:
    return badge(humanize(category), DECISION_COLORS.get(category, "gray"))


def review_badge(status: str) -> str:
    return badge(humanize(status), REVIEW_COLORS.get(status, "gray"))


def role_badge(role: str) -> str:
    return badge(str(role).upper(), ROLE_COLORS.get(str(role), "gray"))


def humanize(value: str) -> str:
    return str(value).replace("_", " ").capitalize()


def domain_label(domain_value: str) -> str:
    try:
        return get_domain_label(BankingDomain(domain_value))
    except ValueError:
        return domain_value


def severity_rank(severity: str) -> int:
    s = str(severity).lower()
    return SEVERITY_ORDER.index(s) if s in SEVERITY_ORDER else len(SEVERITY_ORDER)
