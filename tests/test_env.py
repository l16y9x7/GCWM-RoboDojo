"""Environment settings: ``ROBOSKYLAR_*`` variables, read by the package."""

from __future__ import annotations

from roboskylar._env import setting, setting_var
from roboskylar.generate import provider_overrides


def test_setting_reads_the_roboskylar_variable_else_the_default(monkeypatch):
    monkeypatch.delenv("ROBOSKYLAR_PRIMITIVES", raising=False)
    assert setting("PRIMITIVES", "full") == "full"
    assert setting_var("PRIMITIVES") == "ROBOSKYLAR_PRIMITIVES"
    monkeypatch.setenv("ROBOSKYLAR_PRIMITIVES", "no-vla")
    assert setting("PRIMITIVES", "full") == "no-vla"
    monkeypatch.setenv("ROBOSKYLAR_PRIMITIVES", "")  # set but empty still counts as set
    assert setting("PRIMITIVES", "no-vla") == ""


def test_codex_retries_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ROBOSKYLAR_CODEX_RETRIES", "7")
    joined = " ".join(provider_overrides("https://gw.example.com", "KEY"))
    assert "request_max_retries=7" in joined and "stream_max_retries=7" in joined
