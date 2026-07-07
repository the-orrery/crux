"""recall query 粗分类 —— exploratory / precise / mixed,给 `crux stats` 的用量观测。

为什么 = recall limit-sweep:recall 默认 --limit 定档 10,留了「探索型 query 占比上升→可上调到
12」的口子;这个分类把那个触发信号变成可见的数。exploratory(中文低锚:靠语义吃饭)
是会从更深召回位受益的那类;precise(代码符号密集)只认前几位。

分类口径**忠实镜像** memex `planner.py`(`is_zh_low_anchor` / `is_strongly_anchored`)
—— 那里是检索引擎的真相(同一判定驱动 semantic 加权)。这里小幅复刻(~40 行纯 stdlib)
是为了让 `crux stats` 自洽、不在观测路径里 subprocess 调 memex;判定简单且稳定,
漂移风险低。改判定口径时两处一起改。

三桶互斥:zh_low_anchor 要求 ascii_identifier==0 → code_token 必然 0 → 不可能同时
strongly_anchored;两者都不沾 = mixed。
"""

from __future__ import annotations

# is_cjk_char 的 range(镜像 memex planner.py)。
_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2F800, 0x2FA1F),
)

# recall 的 value-flags(后跟一个值);提取 positional query 时跳过 flag+值。
_VALUE_FLAGS = frozenset(
    {"--limit", "--repo", "--domain", "--kind", "--tag", "--lane", "--format"}
)

# ALL_CAPS token 计入 code-token 的最短长度(单字母大写多是英文句首,非符号)。
_MIN_ALLCAPS_LEN = 2


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _is_ascii_ident_start(ch: str) -> bool:
    return ch.isascii() and (ch.isalpha() or ch == "_")


def _is_ascii_ident_continue(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch in "_:-")


def _cjk_count(query: str) -> int:
    return sum(1 for ch in query if _is_cjk(ch))


def _ascii_ident_runs(query: str) -> list[str]:
    runs: list[str] = []
    n, i = len(query), 0
    while i < n:
        if _is_ascii_ident_start(query[i]):
            start = i
            i += 1
            while i < n and _is_ascii_ident_continue(query[i]):
                i += 1
            runs.append(query[start:i])
        else:
            i += 1
    return runs


def _is_code_token(tok: str) -> bool:
    """代码符号 token:含 数字/`_`/`:`/`-`,或 camelCase,或 ALL_CAPS(len≥2)。"""
    if any(ch.isdigit() or ch in "_:-" for ch in tok):
        return True
    has_lower = any(ch.islower() for ch in tok)
    has_upper = any(ch.isupper() for ch in tok)
    if has_lower and has_upper:
        return True
    return has_upper and not has_lower and len(tok) >= _MIN_ALLCAPS_LEN


def is_zh_low_anchor(query: str) -> bool:
    """中文低锚(探索型):有 CJK 且无 ascii identifier token。"""
    return _cjk_count(query) > 0 and len(_ascii_ident_runs(query)) == 0


def is_strongly_anchored(query: str, min_code_tokens: int = 2) -> bool:
    """强锚定(精确型):代码符号 token ≥ 阈值(object_id/uuid_v5/CHUNKED_EMBEDDING…)。"""
    return (
        sum(1 for t in _ascii_ident_runs(query) if _is_code_token(t)) >= min_code_tokens
    )


def classify(query: str) -> str:
    """exploratory(中文低锚)| precise(强锚定)| mixed(其余)。互斥见模块 docstring。"""
    if is_zh_low_anchor(query):
        return "exploratory"
    if is_strongly_anchored(query):
        return "precise"
    return "mixed"


def recall_query_from_args(args: list) -> str | None:
    """从 telemetry 存的 recall args 提 positional query(跳过 flag 与 flag 值)。"""
    i, n = 0, len(args)
    while i < n:
        a = str(args[i])
        if a.startswith("-"):
            i += 1 if ("=" in a or a not in _VALUE_FLAGS) else 2
        else:
            return a
    return None


# recall limit-sweep 重审触发基线。公开发行版只带示例基线;使用者可按本地统计更新。
SWEEP_BASELINE_SWEPT_AT = "1970-01-01"
SWEEP_BASELINE_UNIQUE = 70
SWEEP_BASELINE_EXPLORATORY_PCT = 20.0
SWEEP_TRIGGER_NEW_UNIQUE = 130  # 独立 query 净增到足够样本量才建议重审
SWEEP_TRIGGER_RATIO_SHIFT_PCT = 15.0  # exploratory 占比偏移(可能翻盘 limit 决策)


def sweep_due(unique_queries: int, exploratory_pct: float) -> str | None:
    """够不够触发 recall limit-sweep 重审。返回提示串或 None(未越线)。"""
    reasons: list[str] = []
    grew = unique_queries - SWEEP_BASELINE_UNIQUE
    if grew >= SWEEP_TRIGGER_NEW_UNIQUE:
        reasons.append(f"独立 query +{grew}(阈 +{SWEEP_TRIGGER_NEW_UNIQUE})")
    # 比例触发要等近端样本攒够基线规模(SWEEP_BASELINE_UNIQUE)才比:薄样本里一条
    # query 的归类就让占比剧烈摆动(12 条的 exploratory% 无统计意义→误报)。只有
    # unique ≥ 基线 N 才与上次基线 apples-to-apples。(grew 触发本就 ≥130 不受影响)
    if (
        unique_queries >= SWEEP_BASELINE_UNIQUE
        and abs(exploratory_pct - SWEEP_BASELINE_EXPLORATORY_PCT)
        >= SWEEP_TRIGGER_RATIO_SHIFT_PCT
    ):
        reasons.append(
            f"exploratory {exploratory_pct:.0f}% vs 基线 {SWEEP_BASELINE_EXPLORATORY_PCT:.0f}%"
        )
    if not reasons:
        return None
    return (
        f"⚠ recall-limit sweep 建议重审({' · '.join(reasons)};"
        f"基线 {SWEEP_BASELINE_SWEPT_AT})"
    )
