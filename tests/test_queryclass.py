from __future__ import annotations

from crux import queryclass


def test_exploratory_zh_low_anchor() -> None:
    # 纯中文、无 ascii identifier → 探索型。
    assert queryclass.classify("知识库检索机制") == "exploratory"
    assert queryclass.classify("用户问检索结果怎么排序") == "exploratory"


def test_precise_strong_anchor() -> None:
    # ≥2 个代码符号 token → 精确型。
    assert queryclass.classify("object_id uuid_v5 CHUNKED_EMBEDDING") == "precise"
    assert queryclass.classify("fetchItem DocumentReadServiceImpl") == "precise"


def test_mixed_when_neither() -> None:
    # 中文 + 单个 ascii 词:非低锚(有 identifier)、非强锚(<2 code token)→ mixed。
    assert queryclass.classify("检索系统 v1") == "mixed"
    assert queryclass.classify("search template") == "mixed"


def test_buckets_mutually_exclusive() -> None:
    # zh_low_anchor 与 strongly_anchored 不可能同真(见 queryclass docstring)。
    for q in ["知识库检索机制", "object_id uuid_v5", "检索系统 v1", "hello world"]:
        assert not (
            queryclass.is_zh_low_anchor(q) and queryclass.is_strongly_anchored(q)
        )


def test_recall_query_from_args_positional_first() -> None:
    assert (
        queryclass.recall_query_from_args(["检索系统 索引机制"]) == "检索系统 索引机制"
    )
    assert (
        queryclass.recall_query_from_args(["检索 系统", "--limit", "5"]) == "检索 系统"
    )


def test_recall_query_from_args_skips_leading_value_flags() -> None:
    assert queryclass.recall_query_from_args(["--limit", "8", "查询词"]) == "查询词"
    assert queryclass.recall_query_from_args(["--lane=hybrid", "查询词"]) == "查询词"


def test_recall_query_from_args_none_when_no_positional() -> None:
    assert queryclass.recall_query_from_args(["--limit", "5"]) is None
    assert queryclass.recall_query_from_args([]) is None


def test_sweep_due_silent_under_thresholds() -> None:
    # 基线附近、无显著增量/漂移 → 不触发。
    base_n = queryclass.SWEEP_BASELINE_UNIQUE
    base_p = queryclass.SWEEP_BASELINE_EXPLORATORY_PCT
    assert queryclass.sweep_due(base_n + 10, base_p + 3) is None


def test_sweep_due_fires_on_volume() -> None:
    base_n = queryclass.SWEEP_BASELINE_UNIQUE
    base_p = queryclass.SWEEP_BASELINE_EXPLORATORY_PCT
    msg = queryclass.sweep_due(base_n + queryclass.SWEEP_TRIGGER_NEW_UNIQUE, base_p)
    assert msg is not None and "独立 query" in msg


def test_sweep_due_fires_on_ratio_shift() -> None:
    base_n = queryclass.SWEEP_BASELINE_UNIQUE
    base_p = queryclass.SWEEP_BASELINE_EXPLORATORY_PCT
    msg = queryclass.sweep_due(
        base_n, base_p + queryclass.SWEEP_TRIGGER_RATIO_SHIFT_PCT
    )
    assert msg is not None and "exploratory" in msg


def test_sweep_due_ratio_gated_on_min_sample() -> None:
    # 薄样本(< 基线 70)即使占比极端也不触发 ratio —— 12 条 query 的 exploratory%
    # 无统计意义, 防误报。
    assert queryclass.sweep_due(12, 100.0) is None
    # 攒够基线规模才与基线占比 apples-to-apples 比, 此时才触发。
    assert queryclass.sweep_due(queryclass.SWEEP_BASELINE_UNIQUE, 100.0) is not None
