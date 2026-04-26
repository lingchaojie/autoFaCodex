from pathlib import Path

import pytest

from autofacodex.agents.codex_auth import CodexAuthConfig, validate_codex_auth


def test_validate_codex_auth_accepts_auth_and_config(tmp_path: Path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"ok":true}', encoding="utf-8")
    (codex_home / "config.toml").write_text(
        'model = "gpt-5.3-codex"\n', encoding="utf-8"
    )

    config = validate_codex_auth(
        CodexAuthConfig(codex_home=codex_home, codex_bin="codex")
    )

    assert config.auth_json == codex_home / "auth.json"
    assert config.config_toml == codex_home / "config.toml"


def test_validate_codex_auth_rejects_missing_auth(tmp_path: Path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    with pytest.raises(FileNotFoundError, match="auth.json"):
        validate_codex_auth(CodexAuthConfig(codex_home=codex_home, codex_bin="codex"))
