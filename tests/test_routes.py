from pathlib import Path

from crux.config import Settings
from crux.routes import resolve


def test_recall_routes_to_memex(monkeypatch) -> None:
    monkeypatch.setenv("CRUX_MEMEX_PROJECT", "/tmp/kbs")
    cmd = resolve("recall", ["查询词", "--limit", "3"], Settings())
    assert cmd[:5] == ["uv", "run", "--quiet", "--project", "/tmp/kbs"]
    assert cmd[5:7] == ["memex", "recall"]
    assert cmd[7:] == ["查询词", "--limit", "3"]


def test_recall_default_project_dir() -> None:
    cmd = resolve("recall", ["q"], Settings())
    assert cmd[4] == str(Path.home() / "workspace" / "memex")


def test_pm_routes_to_docket_without_repeating_verb() -> None:
    cmd = resolve("pm", ["active"], Settings())
    assert cmd == ["docket", "active"]


def test_bare_pm_defaults_to_overview() -> None:
    # surface advertises `crux pm` as the full board; bare docket only prints
    # usage, so the pm route fills in `overview` when no args are given.
    cmd = resolve("pm", [], Settings())
    assert cmd == ["docket", "overview"]


def test_pm_tier_only_defaults_to_overview() -> None:
    cmd = resolve("pm", ["--tier", "work"], Settings())
    assert cmd == ["docket", "--tier", "work", "overview"]


def test_pm_tier_equals_only_defaults_to_overview() -> None:
    cmd = resolve("pm", ["--tier=personal"], Settings())
    assert cmd == ["docket", "--tier=personal", "overview"]


def test_pm_tier_with_subcommand_does_not_inject_default() -> None:
    cmd = resolve("pm", ["--tier", "work", "active"], Settings())
    assert cmd == ["docket", "--tier", "work", "active"]


def test_pm_help_does_not_inject_default() -> None:
    cmd = resolve("pm", ["--help"], Settings())
    assert cmd == ["docket", "--help"]


def test_pm_tier_missing_value_does_not_inject_default() -> None:
    cmd = resolve("pm", ["--tier"], Settings())
    assert cmd == ["docket", "--tier"]


def test_unknown_verb_resolves_none() -> None:
    assert resolve("doc", ["list"], Settings()) is None


def test_docket_bin_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CRUX_DOCKET_BIN", "/tmp/fake-docket")
    cmd = resolve("pm", ["active"], Settings())
    assert cmd == ["/tmp/fake-docket", "active"]
