"""crux telemetry — thin binding over gnomon core + crux's recall-query
analysis.

crux is a subprocess dispatch shell (children write fds directly, not through
crux's Python layer), so it uses the `record` posture — it assembles each row
itself (times the run, collects fields) and delegates the write; it never uses
gnomon.run_instrumented's in-process capture.

The shared core (schema / connect / record / stats / percentiles) lives in
gnomon under an IDENTICAL `calls` schema, so tool ledgers can be unioned
for cross-tool analysis. Only crux's recall-query mix / sweep-due alert stay here.
The recall mix is appended to the standard stats report at THIS call layer
(A2 — core doesn't grow a hook for it).
"""

from __future__ import annotations

import json
from pathlib import Path

import gnomon as ot

from crux import __version__

CFG = ot.Cfg(tool="crux", version=__version__)

# re-export the core db primitives so crux modules read crux's own ledger without
# re-opening it (sweep_alert / stats below, and concurrency tests).
connect = ot.connect


def db_path() -> Path:
    return ot.db_path(CFG)


def record(rec: dict, *, path: Path | None = None) -> None:
    """crux assembles the row itself (subprocess shell), then delegates the write
    to the shared core under crux's Cfg. Best-effort lives in the core."""
    ot.record(rec, CFG, path=path)


# ---- crux domain: recall-query mix / sweep-due alert (never in the core) ----


def _classify_recall(recall_args: list) -> tuple[int, set[str], dict[str, int]]:
    """recall args 列表 → (分类成功的 call 数, 去重 query 集, 三桶计数)。"""
    from crux import queryclass

    buckets = {"exploratory": 0, "precise": 0, "mixed": 0}
    n = 0
    seen: set[str] = set()
    for (raw,) in recall_args:
        try:
            args = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        q = queryclass.recall_query_from_args(args if isinstance(args, list) else [])
        if not q:
            continue
        buckets[queryclass.classify(q)] += 1
        n += 1
        seen.add(q)
    return n, seen, buckets


def _recall_query_mix(recall_args: list) -> str | None:
    """成功 recall 的 query 粗分类计数(recall limit-sweep 探索比例探针)。无可分类则 None。"""
    from crux import queryclass

    n, seen, buckets = _classify_recall(recall_args)
    if not n:
        return None
    pct = {k: 100.0 * v / n for k, v in buckets.items()}
    line = (
        f"recall query mix ({n} calls, {len(seen)} unique): "
        f"exploratory {pct['exploratory']:.0f}% · "
        f"precise {pct['precise']:.0f}% · "
        f"mixed {pct['mixed']:.0f}%"
    )
    due = queryclass.sweep_due(len(seen), pct["exploratory"])
    return f"{line}\n{due}" if due else line


def _recall_args(path: Path) -> list:
    """Pull successful-recall arg rows from the ledger. Best-effort → [] on any miss."""
    try:
        if not path.exists():
            return []
        conn = connect(path)
        try:
            return conn.execute(
                "SELECT args FROM calls"
                " WHERE json_extract(command_path, '$[0]') = 'recall'"
                " AND exit_code = 0"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def sweep_alert(path: Path | None = None) -> str | None:
    """recall limit-sweep 重审触发提示(越线才非 None), 供 SessionStart surface 主动露出。
    Best-effort: 任何读失败/无数据返回 None —— surface 注入绝不能因 telemetry 炸而拖垮启动。"""
    rows = _recall_args(path or db_path())
    if not rows:
        return None
    try:
        from crux import queryclass

        n, _seen, buckets = _classify_recall(rows)
        if not n:
            return None
        return queryclass.sweep_due(len(_seen), 100.0 * buckets["exploratory"] / n)
    except Exception:
        return None


def stats(path: Path | None = None) -> str:
    """通用报表(core)+ crux 领域段 recall-query mix。

    A2(调用层拼): core 的 stats 只出标准报表, crux 在这里把领域段接在其后 —
    core 不为此长 hook。领域段位置由「接在末尾」决定(可接受)。"""
    p = path or db_path()
    base = ot.stats(CFG, path=path)
    mix = _recall_query_mix(_recall_args(p))
    return f"{base}\n\n{mix}" if mix else base
