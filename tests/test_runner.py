from __future__ import annotations

import json
import subprocess

import pytest

from nat.plugins.hol_guard.runner import build_tool_input
from nat.plugins.hol_guard.runner import evaluate_pretool_event


def test_build_tool_input_preserves_named_command() -> None:
    payload = build_tool_input((), {"command": "git status", "cwd": "/tmp/project"})
    assert payload == {"command": "git status", "cwd": "/tmp/project"}


def test_build_tool_input_preserves_mapping_positional_arg() -> None:
    payload = build_tool_input(({"path": "/tmp/file", "mode": "write"},), {})
    assert payload == {"path": "/tmp/file", "mode": "write"}


def test_block_exit_code_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        event_path = command[command.index("--event-file") + 1]
        with open(event_path, encoding="utf-8") as handle:
            seen.update(json.load(handle))
        return subprocess.CompletedProcess(command, 1, stdout='{"reason":"blocked by policy"}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    decision = evaluate_pretool_event(
        executable="hol-guard",
        tool_name="shell",
        args=(),
        kwargs={"command": "rm -rf /tmp/example"},
        timeout_seconds=2.0,
    )

    assert decision.blocked is True
    assert decision.returncode == 1
    assert decision.reason == "blocked by policy"
    assert seen["hook_event_name"] == "PreToolUse"
    assert seen["tool_name"] == "shell"
    assert seen["tool_input"] == {"command": "rm -rf /tmp/example"}


def test_allow_exit_code_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    decision = evaluate_pretool_event(
        executable="hol-guard",
        tool_name="read_file",
        args=(),
        kwargs={"path": "README.md"},
        timeout_seconds=2.0,
    )
    assert decision.blocked is False
    assert decision.returncode == 0
