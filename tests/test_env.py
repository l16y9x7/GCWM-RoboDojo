"""Environment settings: ``ROBODOJO_*`` variables, read by the package."""

from __future__ import annotations

from robodojo._env import setting, setting_var
from robodojo.generate import provider_overrides


def test_setting_reads_the_robodojo_variable_else_the_default(monkeypatch):
    monkeypatch.delenv("ROBODOJO_PRIMITIVES", raising=False)
    assert setting("PRIMITIVES", "full") == "full"
    assert setting_var("PRIMITIVES") == "ROBODOJO_PRIMITIVES"
    monkeypatch.setenv("ROBODOJO_PRIMITIVES", "no-vla")
    assert setting("PRIMITIVES", "full") == "no-vla"
    monkeypatch.setenv("ROBODOJO_PRIMITIVES", "")  # set but empty still counts as set
    assert setting("PRIMITIVES", "no-vla") == ""


def test_codex_retries_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ROBODOJO_CODEX_RETRIES", "7")
    joined = " ".join(provider_overrides("https://gw.example.com", "KEY"))
    assert "request_max_retries=7" in joined and "stream_max_retries=7" in joined
