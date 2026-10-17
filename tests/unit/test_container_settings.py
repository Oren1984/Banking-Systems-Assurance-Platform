from __future__ import annotations

from pathlib import Path

from core.config import Settings

# Docker Compose only interpolates ${VAR} from the shell or deployment/.env,
# never from the root .env that both containers load. The app previously
# built DATABASE_URL by interpolation, so it silently used a different
# password than the database volume. These tests pin the replacement: the
# app derives its connection from the same .env values as the db service.

COMPOSE = Path(__file__).resolve().parents[2] / "deployment" / "docker-compose.yml"


def _container(**env) -> Settings:
    base = dict(
        _env_file=None,
        database_url="",
        allowed_scan_paths="",
        postgres_host="db",
        postgres_password="s3cret/with:special@chars",
    )
    base.update(env)
    return Settings(**base)


def test_database_url_is_built_from_postgres_settings_in_the_container():
    s = _container(postgres_user="bank_user", postgres_db="bank_db")
    assert s.database_url == "postgresql://bank_user:s3cret%2Fwith%3Aspecial%40chars@db:5432/bank_db"


def test_scan_paths_come_from_docker_allowed_scan_paths_in_the_container():
    s = _container(docker_allowed_scan_paths="/scan-targets/a, /scan-targets/b")
    assert s.allowed_scan_paths == ["/scan-targets/a", "/scan-targets/b"]


def test_explicit_values_win_outside_the_container():
    s = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost:5434/d",
        allowed_scan_paths="mock_banking_system",
        postgres_password="other",
        docker_allowed_scan_paths="/scan-targets/a",
    )
    assert s.database_url == "postgresql://u:p@localhost:5434/d"
    assert s.allowed_scan_paths == ["mock_banking_system"]


def test_nothing_is_derived_without_postgres_host():
    s = Settings(_env_file=None, postgres_password="x", docker_allowed_scan_paths="/scan-targets/a")
    assert s.database_url is None
    assert s.allowed_scan_paths == []


def test_compose_never_interpolates_the_database_password():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "${POSTGRES_PASSWORD" not in text
    assert text.count("- ../.env") == 2  # db and app read the same file
