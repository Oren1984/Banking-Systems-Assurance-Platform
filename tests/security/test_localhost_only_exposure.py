from __future__ import annotations

import re
from pathlib import Path

# This delivery is local-only: every port Docker Compose publishes must be
# bound to the host's loopback interface. Publishing to all interfaces (a
# bare "8501:8501") would expose the plain-HTTP UI and the database to the
# network. Enabling remote access requires HTTPS first — see README.md.

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "deployment" / "docker-compose.yml"
ENTRYPOINT = REPO_ROOT / "deployment" / "docker-entrypoint.sh"


def _published_ports() -> list[str]:
    ports, in_ports = [], False
    for line in COMPOSE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("ports:"):
            in_ports = True
            continue
        if in_ports:
            m = re.match(r'-\s*"?([^"]+)"?$', stripped)
            if m and not stripped.startswith("#"):
                ports.append(m.group(1))
                continue
            in_ports = False
    return ports


def test_every_published_port_is_bound_to_localhost():
    ports = _published_ports()
    assert ports, "expected the app and db services to publish ports"
    for port in ports:
        assert port.startswith("127.0.0.1:"), f"port mapping {port!r} is not localhost-only"


def test_container_runs_the_authenticated_entrypoint():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    assert "streamlit run ui/app.py" in text
