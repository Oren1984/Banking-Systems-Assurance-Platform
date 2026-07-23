from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.config import Settings
from governance.retention import ScanRetentionSnapshot, find_scans_eligible_for_retention

# Phase 4 — governance/retention.py ("retention foundations"). Pure
# function, no database, no deletion — see the module's own docstring for
# exactly what is and is not in scope here.


def test_retention_disabled_by_default_in_settings():
    settings = Settings(_env_file=None)
    assert settings.data_retention_days is None


def test_no_scans_eligible_when_retention_days_is_none():
    now = datetime.now(timezone.utc)
    scans = [ScanRetentionSnapshot(scan_id="s1", created_at=now - timedelta(days=9999))]
    assert find_scans_eligible_for_retention(scans, retention_days=None, as_of=now) == []


def test_scan_older_than_retention_window_is_eligible():
    now = datetime.now(timezone.utc)
    old_scan = ScanRetentionSnapshot(scan_id="old", created_at=now - timedelta(days=100))
    recent_scan = ScanRetentionSnapshot(scan_id="recent", created_at=now - timedelta(days=1))
    candidates = find_scans_eligible_for_retention([old_scan, recent_scan], retention_days=90, as_of=now)
    assert [c.scan_id for c in candidates] == ["old"]
    assert candidates[0].age_days >= 90


def test_scan_exactly_at_the_boundary_is_eligible():
    now = datetime.now(timezone.utc)
    scan = ScanRetentionSnapshot(scan_id="boundary", created_at=now - timedelta(days=90))
    candidates = find_scans_eligible_for_retention([scan], retention_days=90, as_of=now)
    assert [c.scan_id for c in candidates] == ["boundary"]


def test_negative_retention_days_raises():
    with pytest.raises(ValueError):
        find_scans_eligible_for_retention([], retention_days=-1, as_of=datetime.now(timezone.utc))


def test_settings_rejects_negative_retention_days():
    with pytest.raises(Exception):
        Settings(_env_file=None, data_retention_days=-1)
