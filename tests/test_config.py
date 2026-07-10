from pathlib import Path

from crux.config import Settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.memex_bin == "memex"
    assert s.docket_bin == "docket"
    assert s.tools_root == Path.home() / ".config" / "crux" / "tools"


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CRUX_MEMEX_BIN", "/tmp/memex")
    monkeypatch.setenv("CRUX_DOCKET_BIN", "/tmp/docket")
    assert Settings().memex_bin == "/tmp/memex"
    assert Settings().docket_bin == "/tmp/docket"
