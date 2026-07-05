from __future__ import annotations

import os
from pathlib import Path

import pytest

from crux import telemetry


def _rec(verb: str, exit_code: int = 0, duration_ms: int = 10, err: str = "") -> dict:
    return {
        "ts": "2026-01-01T00:00:00.000+00:00",
        "pid": 1,
        "command_path": [verb],
        "args": [],
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "err": err,
    }


def test_record_and_stats_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    for i in range(5):
        telemetry.record(_rec("list", duration_ms=i * 10), path=db)
    telemetry.record(_rec("new", exit_code=2, err="boom"), path=db)
    out = telemetry.stats(path=db)
    assert "list" in out
    assert "new" in out
    assert "6 calls" in out
    assert "boom" in out  # the fault message surfaces in recent errors


def _rec_recall(query: str, exit_code: int = 0) -> dict:
    r = _rec("recall", exit_code=exit_code)
    r["args"] = [query, "--limit", "5"]
    return r


def test_stats_recall_query_mix(tmp_path: Path) -> None:
    db = tmp_path / "mix.db"
    telemetry.record(_rec_recall("知识库检索机制"), path=db)  # exploratory
    telemetry.record(_rec_recall("object_id uuid_v5"), path=db)  # precise
    telemetry.record(_rec_recall("检索系统 v1"), path=db)  # mixed
    telemetry.record(_rec_recall("失败的 query", exit_code=2), path=db)  # 不计(非 0)
    out = telemetry.stats(path=db)
    assert "recall query mix (3 calls, 3 unique)" in out
    assert "exploratory 33%" in out
    assert "precise 33%" in out
    assert "mixed 33%" in out
    assert "建议重审" not in out  # 3 条远未越线


def test_stats_no_mix_line_without_recall(tmp_path: Path) -> None:
    db = tmp_path / "nomix.db"
    telemetry.record(_rec("list"), path=db)
    assert "recall query mix" not in telemetry.stats(path=db)


def test_stats_missing_db(tmp_path: Path) -> None:
    assert "no telemetry yet" in telemetry.stats(path=tmp_path / "absent.db")


def test_disabled_suppresses_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "off.db"
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    telemetry.record(_rec("list"), path=db)
    assert not db.exists()  # nothing written when opted out


def test_record_best_effort_never_raises(tmp_path: Path) -> None:
    bad_parent = tmp_path / "afile"
    bad_parent.write_text("x")  # a file → can't mkdir a dir under it
    telemetry.record(_rec("x"), path=bad_parent / "sub.db")  # must not raise
    assert not (bad_parent / "sub.db").exists()


def test_stats_corrupt_db(tmp_path: Path) -> None:
    db = tmp_path / "bad.db"
    db.write_text("not a database")
    assert "unreadable" in telemetry.stats(path=db)  # human note, never a traceback


def test_concurrent_writes(tmp_path: Path) -> None:
    """Many processes appending at once must not lose or corrupt rows — the whole
    reason for SQLite (WAL + busy_timeout) over a flat jsonl."""
    if not hasattr(os, "fork"):
        pytest.skip("needs fork for true multi-process concurrency")
    import multiprocessing as mp

    db = tmp_path / "c.db"
    telemetry.record(_rec("seed"), path=db)  # create schema once before the race

    per_proc, n_proc = 25, 8

    def worker() -> None:  # fork inherits this closure — no pickling needed
        for _ in range(per_proc):
            telemetry.record(_rec("hit"), path=db)

    ctx = mp.get_context("fork")
    procs = [ctx.Process(target=worker) for _ in range(n_proc)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
        assert p.exitcode == 0

    conn = telemetry.connect(db)
    try:
        total = conn.execute("SELECT count(*) FROM calls").fetchone()[0]
        hits = conn.execute(
            "SELECT count(*) FROM calls WHERE json_extract(command_path, '$[0]') = 'hit'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert hits == per_proc * n_proc  # no lost writes under contention
    assert total == per_proc * n_proc + 1
