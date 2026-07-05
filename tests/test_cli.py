import subprocess
from types import SimpleNamespace

import pytest

from crux import cli
from crux.config import Settings


@pytest.fixture(autouse=True)
def _no_telemetry(monkeypatch):
    monkeypatch.setenv("CRUX_TELEMETRY_OFF", "1")


def _run_cli(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr("sys.argv", ["crux", *argv])
    with pytest.raises(SystemExit) as e:
        cli.run()
    code = e.value.code
    return code if isinstance(code, int) else 0


def test_bare_prints_catalog_exit_2(monkeypatch, capsys) -> None:
    assert _run_cli(monkeypatch, []) == 2
    out = capsys.readouterr().out
    assert "recall" in out and "pm" in out and "surface" in out


def test_unknown_verb_errors_with_surface_hint(monkeypatch, capsys) -> None:
    assert _run_cli(monkeypatch, ["doc", "list"]) == 2
    err = capsys.readouterr().err
    assert "unknown verb 'doc'" in err and "crux surface" in err


def test_help_exit_0(monkeypatch, capsys) -> None:
    assert _run_cli(monkeypatch, ["--help"]) == 0
    assert "recall" in capsys.readouterr().out


def test_dispatch_inherits_stdio_no_env_cwd(monkeypatch) -> None:
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _run_cli(monkeypatch, ["pm", "active"]) == 0
    assert seen["cmd"] == ["docket", "active"]
    assert seen["kwargs"] == {}  # stdio/env/cwd 全继承, 不传任何 kwargs


def test_recall_inherits_stdio_no_env_cwd(monkeypatch) -> None:
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _run_cli(monkeypatch, ["recall", "查询词"]) == 0
    assert seen["cmd"][5:7] == ["memex", "recall"]
    assert seen["kwargs"] == {}  # stdio/env/cwd 全继承, 不注入额外环境变量


def test_exit_code_passthrough(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda _cmd, **_kw: SimpleNamespace(returncode=2)
    )
    assert _run_cli(monkeypatch, ["recall"]) == 2


def test_signal_death_maps_to_128_plus_sig(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda _cmd, **_kw: SimpleNamespace(returncode=-2)
    )
    assert _run_cli(monkeypatch, ["recall", "q"]) == 130


def test_missing_target_exit_127(monkeypatch, capsys) -> None:
    def raise_fnf(cmd, **_kw):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    monkeypatch.setenv("CRUX_DOCKET_BIN", "/nonexistent/docket")
    assert _run_cli(monkeypatch, ["pm", "active"]) == 127
    err = capsys.readouterr().err
    assert "/nonexistent/docket" in err and "pm" in err


def test_telemetry_records_verb_and_target(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CRUX_TELEMETRY_OFF")
    monkeypatch.setenv("CRUX_TELEMETRY_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda _cmd, **_kw: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert _run_cli(monkeypatch, ["pm", "active"]) == 0
    from crux import telemetry

    out = telemetry.stats(tmp_path / "t.db")
    assert "pm" in out


def test_surface_help_prints_usage_exit_0(monkeypatch, capsys) -> None:
    # `crux surface --help` 不再被当成工具名找(旧 bug: tool '--help' not found),
    # 而是打印 surface 用法, 含 --brief。
    assert _run_cli(monkeypatch, ["surface", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--brief" in out and "crux surface" in out
    assert "not found" not in out


def test_catalog_lists_all_routes() -> None:
    out = cli._catalog(Settings())
    assert "stats" in out and "memex" in out and "docket" in out
