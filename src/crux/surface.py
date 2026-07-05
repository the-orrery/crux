"""crux surface — discovery 轴统一:crux verbs + capability surfaces。

注册表 = tools/*/manifest.toml(desc 是 hint 不是手册)。surface 只给
指针,具体使用顺序由 manifest 的 agent.sequence 给出。manifest 解析失败的
surface 仍列出并标注 —— 不静默跳过。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from crux import telemetry
from crux.config import Settings
from crux.routes import routes

LOCAL_VERBS = {
    "surface": "能力面:crux verbs + capability registry(`crux surface <name>` 看详情)",
    "stats": "本地用量统计 (crux 自身)",
}

SURFACE_USAGE = """\
crux surface — LLM-facing 能力面(crux verbs + capability registry)

用法:
  crux surface            全量:越线告警 + crux verbs + capability surfaces(按 domain 分组)
  crux surface --brief    瘦版:仅越线告警 + 一行 pull 指针(SessionStart 注入用)
  crux surface <name>     单个 surface 的 manifest.toml 原文(细节看 agent.sequence)
  crux surface --help     本帮助"""


@dataclass
class Tool:
    name: str
    desc: str = ""
    status: str = ""
    domain: str = ""
    error: str = ""
    path: Path | None = None
    raw: dict = field(default_factory=dict)


def scan_tools(root: Path) -> list[Tool]:
    if not root.is_dir():
        return []
    tools = []
    for d in sorted(root.iterdir()):
        mf = d / "manifest.toml"
        if not d.is_dir() or not mf.is_file():
            continue
        try:
            data = tomllib.loads(mf.read_text())
            tools.append(
                Tool(
                    name=str(data.get("name", d.name)),
                    desc=str(data.get("desc", "")),
                    status=str(data.get("status", "")),
                    domain=str(data.get("domain", "")) or "(无 domain)",
                    path=mf,
                    raw=data,
                )
            )
        except (tomllib.TOMLDecodeError, OSError) as e:
            tools.append(Tool(name=d.name, error=str(e), domain="(无 domain)", path=mf))
    return tools


def render(s: Settings) -> str:
    lines = ["## crux Surface", ""]
    # 越线才露(recall limit-sweep 重审触发);平时 None, 不污染 surface。放最上面最显眼。
    alert = telemetry.sweep_alert()
    if alert:
        lines += [alert, ""]
    lines += ["crux — LLM-facing 统一入口:", ""]
    for verb, r in routes(s).items():
        lines.append(f"- `crux {verb}`: {r.desc}")
    for verb, desc in LOCAL_VERBS.items():
        lines.append(f"- `crux {verb}`: {desc}")
    lines.append("")

    tools = [t for t in scan_tools(s.tools_root) if t.status != "deprecated"]
    if not tools:
        lines.append(f"(surfaces: {s.tools_root} 不存在或为空)")
        return "\n".join(lines)

    lines.append(f"surfaces({len(tools)} 个;`crux surface <name>` 看详情):")
    by_domain: dict[str, list[Tool]] = {}
    for t in tools:
        by_domain.setdefault(t.domain, []).append(t)
    for domain in sorted(by_domain):
        lines.append("")
        lines.append(f"[{domain}]")
        for t in by_domain[domain]:
            note = f"(manifest 解析失败: {t.error})" if t.error else t.desc
            mark = " ⚠experimental" if t.status == "experimental" else ""
            lines.append(f"- {t.name}: {note}{mark}")
    return "\n".join(lines)


def render_brief(_s: Settings) -> str:
    """Session-start 瘦 surface(tiered push):只出越线告警 + pull 指针。

    capability registry(scan_tools)与全量 verbs 是 pull-on-demand —— 走 `crux surface`,
    不在每会话开场常驻。crux 入口的静态 doctrine 在 AGENTS.md;这里只承载
    live/越线的便宜信息(告警)+ 一次 pull 的 nudge。
    """
    lines = ["## crux 入口", ""]
    alert = telemetry.sweep_alert()
    if alert:
        lines += [alert, ""]
    lines.append(
        "能力/状态/知识按需自调:`crux surface`(能力面)· "
        '`crux pm`(工作状态)· `crux recall "<问题>"`(KB 召回)。'
    )
    return "\n".join(lines)


def show(name: str, s: Settings) -> tuple[str, int]:
    """单 surface 详情 = manifest 原文(零加工最忠实)。返回 (输出, exit code)。"""
    for t in scan_tools(s.tools_root):
        if t.name == name and t.path is not None:
            return f"# {t.path}\n\n{t.path.read_text()}", 0
    return f"crux surface: '{name}' not found under {s.tools_root}", 1
