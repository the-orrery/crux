"""Make the suite hermetic against the host environment.

crux's Settings is a pydantic BaseSettings with ``env_prefix="CRUX_"``, so any
CRUX_*-prefixed var overrides a default. The agent session shell exports
CRUX_MEMEX_PROJECT / CRUX_TOOLS_ROOT / CRUX_DOCKET_BIN, which leak into the test
process and break the default-value assertions. Strip every CRUX_* var for each
test; tests that exercise an override set it themselves via monkeypatch.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_crux_env(monkeypatch):
    for var in [k for k in os.environ if k.startswith("CRUX_")]:
        monkeypatch.delenv(var, raising=False)
