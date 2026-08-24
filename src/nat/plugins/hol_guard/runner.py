"""Local subprocess bridge from NeMo Agent Toolkit calls to HOL Guard."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


@dataclasses.dataclass(frozen=True)
class GuardDecision:
    """Normalized result of one HOL Guard pre-tool decision."""

    blocked: bool
    reason: str
    returncode: int


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    """Convert runtime arguments into bounded JSON-safe values for local evaluation."""

    if depth > 8:
        return "<max-depth>"
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item, depth=depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item, depth=depth + 1) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_safe(model_dump(mode="json"), depth=depth + 1)
        except Exception:
            pass
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        try:
            return _json_safe(dataclasses.asdict(value), depth=depth + 1)
        except Exception:
            pass
    text = repr(value)
    if len(text) > 2048:
        text = text[:2048] + "…"
    return text


def build_tool_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Preserve native keyword names so Guard can classify command/path semantics."""

    safe_kwargs = {str(key): _json_safe(value) for key, value in kwargs.items()}
    if len(args) == 1 and not safe_kwargs:
        first = _json_safe(args[0])
        if isinstance(first, dict):
            return first
    if args:
        safe_kwargs["_args"] = [_json_safe(value) for value in args]
    return safe_kwargs


def _reason_from_process(process: subprocess.CompletedProcess[str]) -> str:
    for raw in (process.stdout, process.stderr):
        text = (raw or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text.splitlines()[-1])
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            for key in ("reason", "stopReason", "systemMessage"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:1024]
            hook_output = payload.get("hookSpecificOutput")
            if isinstance(hook_output, dict):
                value = hook_output.get("permissionDecisionReason")
                if isinstance(value, str) and value.strip():
                    return value.strip()[:1024]
        return text.splitlines()[-1][:1024]
    return "HOL Guard denied the function call."


def evaluate_pretool_event(
    *,
    executable: str,
    tool_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    timeout_seconds: float,
) -> GuardDecision:
    """Run one local HOL Guard PreToolUse evaluation.

    HOL Guard's hook contract returns 0 for proceed and 1 for a denied pre-tool
    action. Other exit codes indicate an integration/runtime error and are left to
    the middleware's fail-open/fail-closed policy.
    """

    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": build_tool_input(args, kwargs),
        "source_scope": "project",
    }

    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False) as handle:
            path = handle.name
            os.chmod(path, 0o600)
            json.dump(payload, handle, sort_keys=True, ensure_ascii=True, allow_nan=False)
            handle.write("\n")

        process = subprocess.run(
            [
                executable,
                "hook",
                "--harness",
                "nemo-agent-toolkit",
                "--event-file",
                path,
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    finally:
        if path is not None:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    if process.returncode == 0:
        return GuardDecision(blocked=False, reason="", returncode=0)
    return GuardDecision(
        blocked=process.returncode == 1,
        reason=_reason_from_process(process),
        returncode=process.returncode,
    )
