"""crux — LLM-facing 统一入口: 薄 umbrella + git 式 dispatch。

verb 路由到独立工具(recall→memex, pm→docket), surface/stats 本地。
转发用 subprocess 继承 stdio(不 exec), 换取 telemetry。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from crux import __version__, surface, telemetry
from crux.config import Settings
from crux.routes import resolve, routes


def _catalog(s: Settings) -> str:
    lines = ["crux — LLM-facing 统一入口 (薄壳, git 式 dispatch)", "", "verbs:"]
    for verb, r in routes(s).items():
        lines.append(f"  {verb:<9}{r.desc}")
    for verb, desc in surface.LOCAL_VERBS.items():
        lines.append(f"  {verb:<9}{desc}")
    return "\n".join(lines)


def _dispatch(verb: str, rest: list[str], s: Settings) -> int:
    cmd = resolve(verb, rest, s)
    if cmd is None:
        print(f"crux: unknown verb '{verb}'; 能力面见 `crux surface`", file=sys.stderr)
        return 2
    start = time.monotonic()
    err_msg = ""
    # Ctrl-C 让子进程自己处理, crux 等它退; 否则父进程先死吐 KeyboardInterrupt
    prev = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        # stdio/env/cwd 全继承:子进程可读 stdin(hook payload)且基于当前目录工作。
        rc = subprocess.run(cmd).returncode
    except FileNotFoundError:
        err_msg = f"{cmd[0]} not found (route for '{verb}')"
        print(f"crux: {err_msg}; check CRUX_* env or install target", file=sys.stderr)
        rc = 127
    finally:
        signal.signal(signal.SIGINT, prev)
    if rc < 0:
        rc = 128 - rc  # 被信号杀 → POSIX 惯例 128+sig
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    telemetry.record(
        {
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "pid": os.getpid(),
            "command_path": [verb],
            "args": rest,
            "exit_code": rc,
            "duration_ms": int((time.monotonic() - start) * 1000),
            "err": err_msg,
            "cwd": str(Path.cwd()),
            "version": __version__,
            "is_ci": bool(os.environ.get("CI")),
            "meta": {"target": cmd[0], **({"session": session} if session else {})},
        }
    )
    return rc


def run() -> None:
    argv = sys.argv[1:]
    s = Settings()
    if not argv or argv[0] in ("--help", "-h", "help"):
        print(_catalog(s))
        sys.exit(0 if argv else 2)
    if argv[0] == "stats":
        print(telemetry.stats())
        sys.exit(0)
    if argv[0] == "surface":
        if len(argv) > 1:
            if argv[1] in ("--help", "-h"):
                print(surface.SURFACE_USAGE)
                sys.exit(0)
            if argv[1] == "--brief":
                print(surface.render_brief(s))
                sys.exit(0)
            out, rc = surface.show(argv[1], s)
            print(out, file=sys.stdout if rc == 0 else sys.stderr)
            sys.exit(rc)
        print(surface.render(s))
        sys.exit(0)
    sys.exit(_dispatch(argv[0], argv[1:], s))


if __name__ == "__main__":
    run()
