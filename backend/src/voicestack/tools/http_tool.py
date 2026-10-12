"""HTTP tools: call any REST endpoint from a voice agent.

Config keys: method, url (with {param} placeholders), headers ({{secret:NAME}} allowed),
send_args_as ("json" | "query" | "none"), body_template (JSON string with {param} placeholders),
response_path (one JSONPath) or response_fields ({name: JSONPath}), max_chars, timeout_s.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

import httpx
from jsonpath_ng.ext import parse as jsonpath_parse

from voicestack.config import get_settings
from voicestack.security.ssrf import check_url
from voicestack.tools.secrets import render_secrets

PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _fill(template: str, args: dict[str, Any], *, url: bool) -> tuple[str, set[str]]:
    used: set[str] = set()

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in args:
            return m.group(0)
        used.add(key)
        value = args[key]
        text = value if isinstance(value, str) else json.dumps(value)
        return quote(str(text), safe="") if url else str(text)

    return PLACEHOLDER.sub(repl, template), used


def shape_response(payload: Any, response_path: str | None, max_chars: int, fields: dict[str, str] | None = None) -> str:
    if fields and not isinstance(payload, str):
        picked = {}
        for name, path in fields.items():
            matches = [m.value for m in jsonpath_parse(path).find(payload)]
            picked[name] = matches[0] if len(matches) == 1 else (matches or None)
        payload = picked
    elif response_path:
        matches = [m.value for m in jsonpath_parse(response_path).find(payload)]
        payload = matches[0] if len(matches) == 1 else matches
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + " …[truncated]"
    return text


async def run_http_tool(config: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    method = (config.get("method") or "GET").upper()
    url, used = _fill(config.get("url", ""), args, url=True)
    url = await render_secrets(url)
    await check_url(url)

    headers = {}
    for name, value in (config.get("headers") or {}).items():
        headers[name] = await render_secrets(str(value))

    remaining = {k: v for k, v in args.items() if k not in used}
    send_as = config.get("send_args_as") or ("query" if method in ("GET", "DELETE") else "json")
    params = None
    body: Any = None
    if config.get("body_template"):
        rendered, _ = _fill(config["body_template"], args, url=False)
        body = json.loads(await render_secrets(rendered))
    elif send_as == "json":
        body = remaining
    elif send_as == "query":
        params = {k: v if isinstance(v, str) else json.dumps(v) for k, v in remaining.items()}

    timeout = float(config.get("timeout_s") or settings.tool_timeout_s)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.request(method, url, headers=headers, params=params, json=body if body is not None else None)
    try:
        payload: Any = resp.json()
    except ValueError:
        payload = resp.text
    max_chars = int(config.get("max_chars") or 1500)
    ok = resp.is_success
    shaped = shape_response(
        payload, config.get("response_path") if ok else None, max_chars, config.get("response_fields") if ok else None
    )
    return {"ok": ok, "status": resp.status_code, "result": shaped}
