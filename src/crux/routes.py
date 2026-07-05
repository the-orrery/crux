"""路由表 + 纯函数解析。未知 verb 不兜底转发,resolve 返回 None 由 cli 报错
并指向 `crux surface`。"""

from __future__ import annotations

from dataclasses import dataclass

from crux.config import Settings


@dataclass(frozen=True)
class Route:
    argv: tuple[str, ...]  # 前缀模板, verb 后的参数原样 append
    desc: str  # catalog 一行描述
    default_args: tuple[str, ...] = ()  # 无参时补的子命令 (bare `crux <verb>`)
    option_value_flags: frozenset[str] = frozenset()


def routes(s: Settings) -> dict[str, Route]:
    return {
        "recall": Route(
            (
                "uv",
                "run",
                "--quiet",
                "--project",
                str(s.memex_project),
                "memex",
                "recall",
            ),
            "KB 召回 (memex; 参数见 `crux recall --help`)",
        ),
        # docket 自己用 argv[0] dispatch verb, 所以模板不含 verb。bare `crux pm`
        # 默认 overview = surface 宣传的「全量看板」(否则裸 docket 只吐 usage)。
        "pm": Route(
            (s.docket_bin,),
            "工作状态 (docket)",
            default_args=("overview",),
            option_value_flags=frozenset({"--tier"}),
        ),
    }


def _looks_like_only_global_options(
    rest: list[str], value_flags: frozenset[str]
) -> bool:
    i = 0
    while i < len(rest):
        arg = rest[i]
        if not arg.startswith("-"):
            return False
        if arg in value_flags:
            if i + 1 >= len(rest) or rest[i + 1].startswith("-"):
                return False
            i += 2
            continue
        if any(arg.startswith(f"{flag}=") for flag in value_flags):
            i += 1
            continue
        return False
    return bool(rest)


def resolve(verb: str, rest: list[str], s: Settings) -> list[str] | None:
    r = routes(s).get(verb)
    if r is None:
        return None
    if rest and _looks_like_only_global_options(rest, r.option_value_flags):
        tail = [*rest, *r.default_args]
    else:
        tail = list(rest) if rest else list(r.default_args)
    return [*r.argv, *tail]
