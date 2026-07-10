from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置: env > .env > 默认值。"""

    model_config = SettingsConfigDict(
        env_prefix="CRUX_", env_file=".env", extra="ignore"
    )

    memex_bin: str = "memex"
    docket_bin: str = "docket"
    tools_root: Path = Path.home() / ".config" / "crux" / "tools"
