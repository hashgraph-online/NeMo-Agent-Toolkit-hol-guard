from __future__ import annotations

from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest

import nat.plugins.hol_guard.middleware as middleware_module
from nat.plugin_api import DynamicFunctionMiddleware
from nat.plugins.hol_guard.middleware import HolGuardMiddleware
from nat.plugins.hol_guard.middleware import HolGuardMiddlewareConfig
from nat.plugins.hol_guard.runner import GuardDecision


def _middleware_for_unit_test() -> HolGuardMiddleware:
    middleware = HolGuardMiddleware.__new__(HolGuardMiddleware)
    middleware._hol_guard_config = HolGuardMiddlewareConfig()
    return middleware


def test_config_defaults_to_workflow_function_interception() -> None:
    config = HolGuardMiddlewareConfig()
    assert config.register_workflow_functions is True
    assert config.fail_closed is True


def test_middleware_uses_public_dynamic_middleware_contract() -> None:
    assert issubclass(HolGuardMiddleware, DynamicFunctionMiddleware)


def test_nat_plugin_entry_point_loads() -> None:
    matches = entry_points(group="nat.plugins", name="nat_hol_guard")
    assert len(tuple(matches)) == 1
    loaded = next(iter(matches)).load()
    assert loaded.__name__.endswith("register")


@pytest.mark.asyncio
async def test_blocked_call_never_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    middleware = _middleware_for_unit_test()
    calls = 0

    def fake_evaluate(**_kwargs) -> GuardDecision:
        return GuardDecision(blocked=True, reason="blocked by policy", returncode=1)

    async def call_next(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return "executed"

    monkeypatch.setattr(middleware_module, "evaluate_pretool_event", fake_evaluate)

    with pytest.raises(PermissionError, match="blocked by policy"):
        await middleware.function_middleware_invoke(
            call_next=call_next,
            context=SimpleNamespace(name="shell"),
            command="rm -rf /tmp/example",
        )

    assert calls == 0


@pytest.mark.asyncio
async def test_allowed_call_delegates_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    middleware = _middleware_for_unit_test()
    calls = 0

    def fake_evaluate(**_kwargs) -> GuardDecision:
        return GuardDecision(blocked=False, reason="", returncode=0)

    async def call_next(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return "executed"

    monkeypatch.setattr(middleware_module, "evaluate_pretool_event", fake_evaluate)

    result = await middleware.function_middleware_invoke(
        call_next=call_next,
        context=SimpleNamespace(name="read_file"),
        path="README.md",
    )

    assert result == "executed"
    assert calls == 1
