from __future__ import annotations

from importlib.metadata import entry_points

from nat.plugin_api import DynamicFunctionMiddleware

from nat.plugins.hol_guard.middleware import HolGuardMiddleware
from nat.plugins.hol_guard.middleware import HolGuardMiddlewareConfig


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
