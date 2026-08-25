"""NeMo Agent Toolkit middleware backed by local HOL Guard policy."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from pydantic import Field

from nat.plugin_api import Builder
from nat.plugin_api import DynamicFunctionMiddleware
from nat.plugin_api import DynamicMiddlewareConfig
from nat.plugin_api import FunctionMiddlewareContext

from .runner import GuardDecision
from .runner import evaluate_pretool_event

logger = logging.getLogger(__name__)


class HolGuardMiddlewareConfig(DynamicMiddlewareConfig, name="hol_guard"):
    """Configuration for HOL Guard pre-execution enforcement."""

    register_workflow_functions: bool | None = Field(
        default=True,
        description="Intercept registered workflow functions unless narrowed with workflow_functions.",
    )
    executable: str = Field(default="hol-guard", description="HOL Guard executable available in the environment.")
    timeout_seconds: float = Field(default=10.0, gt=0, le=60, description="Maximum local Guard decision time.")
    fail_closed: bool = Field(
        default=True,
        description="Abort a function call when HOL Guard cannot produce a valid decision.",
    )


class HolGuardMiddleware(DynamicFunctionMiddleware):
    """Evaluate NeMo Agent Toolkit function calls through HOL Guard before execution."""

    def __init__(self, config: HolGuardMiddlewareConfig, builder: Builder):
        super().__init__(config=config, builder=builder)
        self._hol_guard_config = config

    async def _decision(self, *, tool_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> GuardDecision | None:
        config = self._hol_guard_config
        try:
            decision = await asyncio.to_thread(
                evaluate_pretool_event,
                executable=config.executable,
                tool_name=tool_name,
                args=args,
                kwargs=kwargs,
                timeout_seconds=config.timeout_seconds,
            )
        except Exception as exc:
            if config.fail_closed:
                raise RuntimeError("HOL Guard could not evaluate the function call") from exc
            logger.warning("HOL Guard evaluation failed; proceeding because fail_closed=false", exc_info=True)
            return None

        if decision.blocked:
            logger.warning("HOL Guard blocked function '%s': %s", tool_name, decision.reason)
            raise PermissionError(f"HOL Guard blocked function '{tool_name}': {decision.reason}")

        if decision.returncode != 0:
            if config.fail_closed:
                raise RuntimeError(
                    f"HOL Guard returned unexpected exit code {decision.returncode}: {decision.reason}"
                )
            logger.warning(
                "HOL Guard returned exit code %s; proceeding because fail_closed=false: %s",
                decision.returncode,
                decision.reason,
            )
        return decision

    async def function_middleware_invoke(
        self,
        *args: Any,
        call_next,
        context: FunctionMiddlewareContext,
        **kwargs: Any,
    ) -> Any:
        """Enforce HOL Guard before delegating to a non-streaming function."""

        await self._decision(tool_name=context.name, args=args, kwargs=dict(kwargs))
        return await call_next(*args, **kwargs)

    async def function_middleware_stream(
        self,
        *args: Any,
        call_next,
        context: FunctionMiddlewareContext,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Enforce HOL Guard once before delegating to a streaming function."""

        await self._decision(tool_name=context.name, args=args, kwargs=dict(kwargs))
        async for chunk in call_next(*args, **kwargs):
            yield chunk
