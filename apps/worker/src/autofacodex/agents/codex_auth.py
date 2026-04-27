from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexAuthConfig:
    codex_home: Path
    codex_bin: str

    @property
    def auth_json(self) -> Path:
        return self.codex_home / "auth.json"

    @property
    def config_toml(self) -> Path:
        return self.codex_home / "config.toml"


def validate_codex_auth(config: CodexAuthConfig) -> CodexAuthConfig:
    if not config.auth_json.is_file():
        raise FileNotFoundError(
            f"Codex auth file not found: {config.auth_json}. "
            "Mount HOST_CODEX_HOME/auth.json into the Worker container as read-only."
        )
    if not config.config_toml.is_file():
        raise FileNotFoundError(
            f"Codex config file not found: {config.config_toml}. "
            "Mount HOST_CODEX_HOME/config.toml into the Worker container as read-only."
        )
    return config
