from pathlib import Path

import pytest

from crux import queryclass, surface, telemetry
from crux.config import Settings


@pytest.fixture(autouse=True)
def _isolate_telemetry(monkeypatch, tmp_path) -> None:
    # surface.render() 现在读 telemetry 判 sweep alert; 默认指向空 db → alert None,
    # 既隔离真实 ledger 又测了「平时不污染 surface」这条路径。
    monkeypatch.setenv("CRUX_TELEMETRY_DB", str(tmp_path / "absent.db"))


def _mk_tool(root: Path, name: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "manifest.toml").write_text(body)


def _settings(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("CRUX_TOOLS_ROOT", str(tmp_path))
    return Settings()


def test_render_groups_by_domain(tmp_path, monkeypatch) -> None:
    _mk_tool(
        tmp_path,
        "alpha",
        'name = "alpha"\ndesc = "工具甲"\nstatus = "stable"\ndomain = "ops"\n',
    )
    _mk_tool(
        tmp_path,
        "beta",
        'name = "beta"\ndesc = "工具乙"\nstatus = "experimental"\ndomain = "kb"\n',
    )
    out = surface.render(_settings(tmp_path, monkeypatch))
    assert "[ops]" in out and "[kb]" in out
    assert "surfaces(2 个" in out
    assert "alpha: 工具甲" in out
    assert "beta: 工具乙 ⚠experimental" in out
    assert "`crux recall`" in out and "`crux surface`" in out  # verbs 段


def test_render_skips_deprecated(tmp_path, monkeypatch) -> None:
    _mk_tool(
        tmp_path,
        "dead",
        'name = "dead"\ndesc = "x"\nstatus = "deprecated"\ndomain = "ops"\n',
    )
    out = surface.render(_settings(tmp_path, monkeypatch))
    assert "dead" not in out


def test_render_surfaces_parse_errors(tmp_path, monkeypatch) -> None:
    _mk_tool(tmp_path, "broken", "name = [unclosed\n")
    out = surface.render(_settings(tmp_path, monkeypatch))
    assert "broken" in out and "manifest 解析失败" in out  # 不静默跳过


def test_render_missing_root(tmp_path, monkeypatch) -> None:
    s = _settings(tmp_path / "absent", monkeypatch)
    out = surface.render(s)
    assert "不存在或为空" in out
    assert "`crux recall`" in out  # verbs 段仍输出, hook 场景不空转


def test_render_no_sweep_alert_normally(tmp_path, monkeypatch) -> None:
    # 空 telemetry(autouse fixture)→ surface 不带重审提示。
    assert "建议重审" not in surface.render(_settings(tmp_path, monkeypatch))


def test_render_shows_sweep_alert_when_crossed(tmp_path, monkeypatch) -> None:
    db = tmp_path / "tele.db"
    monkeypatch.setenv("CRUX_TELEMETRY_DB", str(db))  # 覆盖 autouse 的空 db
    monkeypatch.delenv("CRUX_TELEMETRY_OFF", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    # ratio 触发要求 unique ≥ 基线 70(薄样本门槛);70 条全探索型 → exploratory 100%
    # vs 基线 21% → 越线。
    for i in range(queryclass.SWEEP_BASELINE_UNIQUE):
        telemetry.record(
            {
                "command_path": ["recall"],
                "args": [f"查询样本变体{chr(0x4E00 + i)}"],
                "exit_code": 0,
            },
            path=db,
        )
    out = surface.render(_settings(tmp_path, monkeypatch))
    assert "建议重审" in out and "exploratory" in out


def test_brief_is_pointer_only_no_catalog(tmp_path, monkeypatch) -> None:
    # brief = pull 指针, 不含工具目录(catalog 走 pull `crux surface`)。
    _mk_tool(
        tmp_path,
        "alpha",
        'name = "alpha"\ndesc = "工具甲"\nstatus = "stable"\ndomain = "ops"\n',
    )
    out = surface.render_brief(_settings(tmp_path, monkeypatch))
    assert "`crux surface`" in out and "`crux pm`" in out and "`crux recall" in out
    assert "工具甲" not in out and "[ops]" not in out  # 目录不常驻
    assert "建议重审" not in out  # 空 telemetry → 无告警


def test_brief_shows_sweep_alert_when_crossed(tmp_path, monkeypatch) -> None:
    db = tmp_path / "tele.db"
    monkeypatch.setenv("CRUX_TELEMETRY_DB", str(db))  # 覆盖 autouse 的空 db
    monkeypatch.delenv("CRUX_TELEMETRY_OFF", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    for i in range(queryclass.SWEEP_BASELINE_UNIQUE):
        telemetry.record(
            {
                "command_path": ["recall"],
                "args": [f"查询样本变体{chr(0x4E00 + i)}"],
                "exit_code": 0,
            },
            path=db,
        )
    out = surface.render_brief(_settings(tmp_path, monkeypatch))
    assert "建议重审" in out and "exploratory" in out


def test_brief_no_alert_on_thin_sample(tmp_path, monkeypatch) -> None:
    # 薄样本(<70 unique)即使全探索型也不该误报 —— ratio gate(真实 ~12 query
    # session 的实况)。
    db = tmp_path / "tele.db"
    monkeypatch.setenv("CRUX_TELEMETRY_DB", str(db))
    monkeypatch.delenv("CRUX_TELEMETRY_OFF", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    for q in [
        "接口设计机制",
        "系统模板生成",
        "缓存淘汰策略",
        "数据流转链路",
        "任务调度模型",
    ]:
        telemetry.record(
            {"command_path": ["recall"], "args": [q], "exit_code": 0}, path=db
        )
    assert "建议重审" not in surface.render_brief(_settings(tmp_path, monkeypatch))


def test_show_found_and_missing(tmp_path, monkeypatch) -> None:
    _mk_tool(tmp_path, "alpha", 'name = "alpha"\ndesc = "工具甲"\n')
    s = _settings(tmp_path, monkeypatch)
    out, rc = surface.show("alpha", s)
    assert rc == 0 and 'desc = "工具甲"' in out and "manifest.toml" in out
    out, rc = surface.show("nope", s)
    assert rc == 1 and "not found" in out
