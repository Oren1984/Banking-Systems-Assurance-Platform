from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Patterns that would indicate a real-looking secret was accidentally
# committed into the example env file. This is a guard against exactly the
# insecure-default anti-pattern found in
# ai-project-control-tower/app/core/config.py:89 during the audit
# (see BANKING_PLATFORM_INTEGRATION_PLAN.md §10, finding #4).
_SUSPICIOUS_FRAGMENTS = [
    "control_tower_pass",
    "sk-",
    "AKIA",
    "ghp_",
]


def test_env_example_exists():
    assert (REPO_ROOT / ".env.example").exists()


def test_env_example_has_no_real_looking_secrets():
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for fragment in _SUSPICIOUS_FRAGMENTS:
        assert fragment not in content, f"suspicious fragment found: {fragment!r}"


def test_env_example_api_keys_are_empty():
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith(("OPENAI_API_KEY=", "GEMINI_API_KEY=", "CLAUDE_API_KEY=")):
            _, _, value = line.partition("=")
            assert value.strip() == ""


def test_env_example_external_providers_disabled_by_default():
    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "EXTERNAL_PROVIDERS_ENABLED=false" in content
    assert "LOCAL_ONLY_MODE=true" in content


def test_no_real_dotenv_file_committed():
    # A real .env must never be committed; only .env.example is. A local,
    # untracked .env is expected — Docker Compose requires it (see README).
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert tracked.returncode != 0, ".env is tracked by git"
    ignored = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=REPO_ROOT)
    assert ignored.returncode == 0, ".env must be git-ignored"
