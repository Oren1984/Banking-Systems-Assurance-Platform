from __future__ import annotations

from governance.secret_masker import mask_secrets


def test_masks_aws_access_key():
    assert "AKIAABCDEFGHIJKLMNOP" not in mask_secrets("key=AKIAABCDEFGHIJKLMNOP")


def test_masks_github_token():
    token = "ghp_" + "a" * 36
    assert token not in mask_secrets(f"token: {token}")


def test_masks_openai_style_key():
    key = "sk-" + "a" * 48
    assert key not in mask_secrets(f"OPENAI_API_KEY={key}")


def test_masks_env_style_secret_but_preserves_key_name():
    # The env-style pattern is line-start-anchored (matches "PASSWORD=...",
    # not an arbitrary "*_PASSWORD=..." suffix) — this is the ported
    # behavior from ai-project-control-tower/app/scanner/secret_masker.py,
    # not a gap introduced here.
    result = mask_secrets("PASSWORD=SuperSecretValue123")
    assert "SuperSecretValue123" not in result
    assert "PASSWORD=" in result


def test_masks_bearer_token_but_preserves_prefix():
    result = mask_secrets("Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789")
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in result
    assert "Bearer" in result


def test_leaves_ordinary_text_untouched():
    text = "This is a normal audit finding with no secrets in it."
    assert mask_secrets(text) == text
