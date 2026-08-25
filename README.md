# HOL Guard for NVIDIA NeMo Agent Toolkit

Provider-owned HOL Guard runtime security middleware for [NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit).

This package follows NeMo Agent Toolkit's third-party plugin model: provider-owned repository, `nat.plugins` entry point, stable imports from `nat.plugin_api`, Apache-2.0 licensing, loader tests, and compatibility CI.

## What it does

`hol_guard` is pre-execution middleware. For intercepted NeMo Agent Toolkit functions it:

1. converts the function name and current arguments into HOL Guard's generic `PreToolUse` event contract;
2. evaluates the event locally with `hol-guard hook --harness nemo-agent-toolkit`;
3. lets return code `0` proceed;
4. maps HOL Guard's deny return code `1` to `InvocationAction.SKIP`, so NeMo Agent Toolkit does not invoke the protected function; and
5. fails closed by default if the local Guard decision cannot be obtained.

HOL Guard remains local-first. This integration does not require Guard Cloud. Coverage depends on the semantics exposed by each tool/function and the active HOL Guard policy.

## Status

This repository is the provider-owned integration requested in [NVIDIA/NeMo-Agent-Toolkit#2176](https://github.com/NVIDIA/NeMo-Agent-Toolkit/issues/2176). It is being prepared for NVIDIA's initial **Listed** third-party plugin review. It is not yet an NVIDIA-listed plugin and is not yet published to PyPI.

The integration currently targets NeMo Agent Toolkit 1.8.x and the opt-in HOL Guard 3.x alpha CLI. HOL Guard is intentionally installed as a separate CLI rather than as a Python dependency of this package. That keeps NeMo Agent Toolkit's Python dependency graph isolated while preserving a narrow local subprocess boundary for Guard decisions.

## Install

### Review/development checkout

Using `uv`:

```bash
git clone https://github.com/hashgraph-online/NeMo-Agent-Toolkit-hol-guard.git
cd NeMo-Agent-Toolkit-hol-guard
uv sync --extra test
uv run pytest
```

Using `pip`:

```bash
git clone https://github.com/hashgraph-online/NeMo-Agent-Toolkit-hol-guard.git
cd NeMo-Agent-Toolkit-hol-guard
python -m pip install -e '.[test]'
pytest
```

Install the HOL Guard 3.x CLI separately so the `hol-guard` executable is on `PATH`, for example with an isolated tool environment:

```bash
pipx install 'hol-guard>=3.0.0a195,<4'
```

After the provider package is approved/listed and published, the intended package installs are:

```bash
uv add nemo-agent-toolkit-hol-guard
# or
pip install nemo-agent-toolkit-hol-guard
```

The provider package itself depends only on the public `nvidia-nat-core` plugin surface. It invokes the separately installed HOL Guard executable at runtime.

## Configure

The registered middleware `_type` is `hol_guard`.

```yaml
middleware:
  hol_guard_runtime:
    _type: hol_guard
    register_workflow_functions: true
    fail_closed: true
    timeout_seconds: 10
```

With `register_workflow_functions: true`, the dynamic middleware registers against workflow functions through NeMo Agent Toolkit's supported middleware API. To narrow interception, set `register_workflow_functions: false` and provide `workflow_functions`.

For function groups or functions that already declare explicit middleware lists, the same named middleware can be referenced using the normal NeMo Agent Toolkit `middleware: [...]` field.

### Minimal workflow placement

Add the middleware block above to a normal NeMo Agent Toolkit workflow configuration. The integration does not replace the workflow or LLM configuration; it wraps the registered workflow functions before invocation. A typical configuration therefore keeps the project's existing `llms`, `workflow`, and function definitions and adds the named `middleware.hol_guard_runtime` entry.

Verify plugin discovery after installation with NeMo Agent Toolkit's component inspection command:

```bash
nat info components
```

The output should include the registered `hol_guard` middleware type.

## Configuration

| Field | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Enable/disable middleware |
| `register_workflow_functions` | `true` | Intercept registered workflow functions |
| `workflow_functions` | unset | Optional explicit function-name list |
| `executable` | `hol-guard` | HOL Guard executable available in the environment |
| `timeout_seconds` | `10` | Maximum local Guard decision time |
| `fail_closed` | `true` | Abort calls on integration/runtime errors |

The remaining dynamic discovery fields are inherited from NeMo Agent Toolkit's public `DynamicMiddlewareConfig`.

## Security boundary

The middleware sends function arguments only to the local `hol-guard` process. Its temporary event file is created with user-only permissions and removed after each decision. No Guard Cloud connection is required.

A deny is enforced before the protected function runs by setting NeMo Agent Toolkit's `InvocationAction.SKIP`. If Guard exits unexpectedly or times out, the integration raises by default rather than silently executing the function. Operators may explicitly set `fail_closed: false` if availability is more important than enforcement.

## Test

```bash
python -m pip install -e '.[test]'
pytest
```

The test suite covers event normalization, allow/deny exit handling, middleware configuration, and entry-point loading. GitHub Actions tests Python 3.11, 3.12, and 3.13 against the declared NeMo Agent Toolkit 1.8 compatibility floor.

## Package metadata

- Repository: `hashgraph-online/NeMo-Agent-Toolkit-hol-guard`
- Planned distribution: `nemo-agent-toolkit-hol-guard`
- Import namespace: `nat.plugins.hol_guard`
- Entry point: `nat_hol_guard = nat.plugins.hol_guard.register`
- Middleware `_type`: `hol_guard`
- Supported NeMo Agent Toolkit line: `>=1.8,<2` (initial review targets 1.8.x)
- License: Apache-2.0
- Support: https://github.com/hashgraph-online/NeMo-Agent-Toolkit-hol-guard/issues
- HOL Guard: https://hol.org/guard

## Support boundary

Please report HOL Guard integration behavior in this repository. Issues in `nvidia-nat-core`, its stable plugin API, or NeMo Agent Toolkit's middleware runtime belong in the upstream NVIDIA repository.
