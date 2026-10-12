"""Code tools: any LangChain tool, registered from Python.

Two ways to add one:
1. Install a package that exposes the entry point group `voicestack.tools`, pointing at a
   LangChain BaseTool, a list of tools, or a callable returning tools.
2. Drop a .py file into PLUGINS_DIR that decorates functions with `@voice_tool`.

Registered tools appear in Integrations → Plugins and can be attached to any agent as kind=plugin.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool, tool

from voicestack.config import get_settings

log = logging.getLogger(__name__)
_REGISTRY: dict[str, BaseTool] = {}
_LOADED = False


def voice_tool(*args: Any, **kwargs: Any) -> Any:
    """Same signature as langchain_core.tools.tool; also registers the tool with Voice Stack."""

    def register(obj: Any) -> BaseTool:
        t = obj if isinstance(obj, BaseTool) else tool(obj, **kwargs)
        _REGISTRY[t.name] = t
        return t

    if args and (callable(args[0]) or isinstance(args[0], BaseTool)) and not kwargs:
        return register(args[0])

    def decorator(fn: Callable[..., Any]) -> BaseTool:
        t = tool(*args, **kwargs)(fn) if args else tool(fn, **kwargs)
        _REGISTRY[t.name] = t
        return t

    return decorator


def _add(obj: Any, source: str) -> None:
    if callable(obj) and not isinstance(obj, BaseTool):
        obj = obj()
    items = obj if isinstance(obj, (list, tuple)) else [obj]
    for item in items:
        if isinstance(item, BaseTool):
            _REGISTRY[item.name] = item
        else:
            log.warning("Ignoring non-tool object from %s: %r", source, item)


def load_plugins(force: bool = False) -> dict[str, BaseTool]:
    global _LOADED
    if _LOADED and not force:
        return _REGISTRY
    for ep in importlib.metadata.entry_points(group="voicestack.tools"):
        try:
            _add(ep.load(), f"entry point {ep.name}")
        except Exception:
            log.exception("Failed to load plugin entry point %s", ep.name)
    plugins_dir = get_settings().plugins_dir
    if plugins_dir and plugins_dir.exists():
        for path in sorted(plugins_dir.glob("*.py")):
            spec = importlib.util.spec_from_file_location(f"voicestack_plugin_{path.stem}", path)
            if not spec or not spec.loader:
                continue
            try:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception:
                log.exception("Failed to load plugin file %s", path)
    _LOADED = True
    return _REGISTRY


def list_plugins() -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "parameters": t.get_input_schema().model_json_schema()}
        for t in load_plugins().values()
    ]


def get_plugin(name: str) -> BaseTool | None:
    return load_plugins().get(name)
