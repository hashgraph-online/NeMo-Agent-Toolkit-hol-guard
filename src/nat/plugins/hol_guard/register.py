"""NeMo Agent Toolkit registration entry point for HOL Guard."""

from __future__ import annotations

from nat.plugin_api import Builder
from nat.plugin_api import register_middleware

from .middleware import HolGuardMiddleware
from .middleware import HolGuardMiddlewareConfig


@register_middleware(config_type=HolGuardMiddlewareConfig)
async def hol_guard_middleware(config: HolGuardMiddlewareConfig, builder: Builder):
    """Build HOL Guard middleware from workflow configuration."""

    yield HolGuardMiddleware(config=config, builder=builder)


__all__ = ["hol_guard_middleware"]
