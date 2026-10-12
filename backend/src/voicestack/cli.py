"""voicestack: run, check, export, and deploy a Voice Stack instance."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer
import yaml

from voicestack.config import PROJECT_ROOT, get_settings

app = typer.Typer(help="Voice Stack: an open-source voice agent builder on xAI's speech-to-speech API.", no_args_is_help=True)
guide_app = typer.Typer(help="The bundled xAI prompting guide.")
prompt_app = typer.Typer(help="Prompt tools.")
sip_app = typer.Typer(help="SIP telephony helpers.")
app.add_typer(guide_app, name="guide")
app.add_typer(prompt_app, name="prompt")
app.add_typer(sip_app, name="sip")
GUIDE_URL = "https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech/prompting-guide.md"


def _ok(msg: str) -> None:
    typer.secho(f"  ok    {msg}", fg="green")


def _warn(msg: str) -> None:
    typer.secho(f"  warn  {msg}", fg="yellow")


def _fail(msg: str) -> None:
    typer.secho(f"  fail  {msg}", fg="red")


@app.command()
def serve(host: str = "0.0.0.0", port: int = int(os.environ.get("PORT", "8000")), reload: bool = False) -> None:
    """Run the API and the built UI."""
    import uvicorn

    uvicorn.run("voicestack.main:app", host=host, port=port, reload=reload, proxy_headers=True, forwarded_allow_ips="*")


@app.command()
def doctor(url: Annotated[str | None, typer.Option(help="Check a running instance at this URL as well")] = None) -> None:
    """Check configuration, database, xAI key, and (optionally) a running instance."""
    from voicestack.security.webhooks import sign, verify

    settings = get_settings()
    failures = 0
    typer.echo("Configuration")
    _ok(f"role={settings.role} auth={settings.auth_mode} env={settings.app_env}")
    if settings.app_env == "production" and not settings.app_encryption_key:
        _fail("APP_ENCRYPTION_KEY is required in production")
        failures += 1
    elif not settings.app_encryption_key:
        _warn("APP_ENCRYPTION_KEY not set; a development key file is used")
    else:
        _ok("APP_ENCRYPTION_KEY set")
    if settings.auth_mode == "token" and not settings.admin_token:
        _fail("AUTH_MODE=token requires ADMIN_TOKEN")
        failures += 1
    if settings.auth_mode == "none" and settings.app_env == "production":
        _warn("AUTH_MODE=none in production: put the app behind an identity-aware proxy or set AUTH_MODE")

    async def checks() -> int:
        nonlocal failures
        from voicestack.credentials import resolve_server_key
        from voicestack.db.session import init_db, session_scope
        from voicestack.xai.client import XAIClient, XAIError

        typer.echo("Database")
        try:
            await init_db()
            async with session_scope() as db:
                key = await resolve_server_key(db)
            _ok(f"{'postgres' if settings.is_postgres else 'sqlite'} reachable")
        except Exception as exc:
            _fail(f"database: {exc}")
            return failures + 1
        typer.echo("xAI")
        if not key:
            _warn(
                "No server-side xAI key (Settings or XAI_API_KEY). Previews can still use a session-only key; telephony cannot."
            )
        else:
            async with XAIClient(key.value) as client:
                try:
                    await client.validate()
                    _ok(f"API key from {key.source} accepted (…{key.value[-4:]})")
                    secret = await client.create_client_secret(60)
                    _ok(f"ephemeral token minted (expires_at={secret.get('expires_at')})")
                    voices = await client.list_voices()
                    _ok(f"{len(voices)} built-in voices: {', '.join(v.get('voice_id', '?') for v in voices[:8])}")
                except XAIError as exc:
                    _fail(f"xAI API: {exc}")
                    failures += 1
        return failures

    failures = asyncio.run(checks())
    typer.echo("Telephony")
    if settings.public_base_url:
        _ok(f"webhook URL {settings.public_base_url.rstrip('/')}/webhooks/xai/call-incoming")
    else:
        _warn("PUBLIC_BASE_URL not set; phone numbers cannot be registered")
    secret = "whsec_" + secrets.token_urlsafe(24)
    body = b'{"type":"realtime.call.incoming"}'
    ts = int(time.time())
    verify(
        secret,
        {"webhook-id": "doctor", "webhook-timestamp": str(ts), "webhook-signature": sign(secret, "doctor", ts, body)},
        body,
    )
    _ok("webhook signature round trip")
    if url:
        typer.echo(f"Instance {url}")
        try:
            r = httpx.get(f"{url.rstrip('/')}/readyz", timeout=10)
            (_ok if r.status_code == 200 else _fail)(f"/readyz -> {r.status_code} {r.text[:120]}")
            failures += r.status_code != 200
        except httpx.HTTPError as exc:
            _fail(f"{url}: {exc}")
            failures += 1
    raise typer.Exit(1 if failures else 0)


@app.command()
def export(out: Annotated[Path | None, typer.Option("-o", help="Write to a file instead of stdout")] = None) -> None:
    """Export the landscape (agents, handoffs, tools, connectors) as YAML."""
    from voicestack.api.landscape import export_landscape
    from voicestack.db.session import init_db, session_scope

    async def run() -> str:
        await init_db()
        async with session_scope() as db:
            return yaml.safe_dump(await export_landscape(db), sort_keys=False, allow_unicode=True)

    text = asyncio.run(run())
    if out:
        out.write_text(text)
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(text)


@app.command()
def apply(file: Annotated[Path, typer.Option("-f", exists=True, help="Landscape YAML")], replace: bool = False) -> None:
    """Create or update agents, handoffs, tools, and connectors from a YAML file."""
    from voicestack.api.landscape import import_landscape
    from voicestack.db.session import init_db, session_scope

    async def run() -> dict:
        await init_db()
        async with session_scope() as db:
            return await import_landscape(db, yaml.safe_load(file.read_text()), replace=replace)

    typer.echo(json.dumps(asyncio.run(run())))


@guide_app.command("refresh")
def guide_refresh() -> None:
    """Re-download the prompting guide the optimiser uses."""
    from datetime import UTC, datetime

    from voicestack.prompting.optimizer import GUIDE_PATH, load_guide

    r = httpx.get(GUIDE_URL, timeout=30, follow_redirects=True)
    r.raise_for_status()
    header = (
        f"<!-- Source: {GUIDE_URL}\n     Fetched: {datetime.now(UTC).date()}. Refresh with `voicestack guide refresh`. -->\n\n"
    )
    GUIDE_PATH.write_text(header + r.text, encoding="utf-8")
    load_guide.cache_clear()
    typer.echo(f"Updated {GUIDE_PATH} ({len(r.text.splitlines())} lines)")


@prompt_app.command("optimize")
def prompt_optimize(
    agent: Annotated[str, typer.Argument(help="Agent slug")],
    mode: Annotated[str, typer.Option(help="align | fix_issue | simplify")] = "align",
    issue: str = "",
) -> None:
    """Rewrite an agent's prompt against the xAI prompting guide and print the result."""
    from sqlalchemy import select

    from voicestack.credentials import resolve_server_key
    from voicestack.db.models import Agent
    from voicestack.db.session import init_db, session_scope
    from voicestack.prompting.compiler import sections_to_text
    from voicestack.prompting.optimizer import optimize_prompt
    from voicestack.runtime.loader import build_agent_spec

    async def run() -> dict:
        await init_db()
        async with session_scope() as db:
            row = (await db.execute(select(Agent).where(Agent.slug == agent))).scalar_one_or_none()
            if not row:
                raise typer.BadParameter(f"No agent with slug {agent!r}")
            key = await resolve_server_key(db)
            if not key:
                raise typer.BadParameter("No xAI key configured")
            spec = await build_agent_spec(db, row)
        return await optimize_prompt(key.value, spec, mode=mode, issue=issue)  # type: ignore[arg-type]

    result = asyncio.run(run())
    typer.echo(f"Lint before: {result['before']['lint']['score']}")
    for i, variant in enumerate(result["variants"], 1):
        typer.secho(f"\n=== Variant {i} (lint {variant['lint_after']['score']}) ===", bold=True)
        typer.echo(sections_to_text(variant["sections"]))
        for change in variant["changes"]:
            typer.echo(f"  - [{change['section']}] {change['change']} ({change['reason']})")
        for warning in variant["warnings"]:
            _warn(warning)


@sip_app.command("simulate")
def sip_simulate(
    to: Annotated[str, typer.Option(help="Dialed number (E.164), must be registered in Telephony")],
    caller: Annotated[str, typer.Option("--from", help="Caller number (E.164)")] = "+14155550100",
    url: str = "http://localhost:8000",
    secret: Annotated[str | None, typer.Option(help="Signing secret; defaults to the stored one for --to")] = None,
    call_id: str | None = None,
) -> None:
    """Send a signed realtime.call.incoming webhook to a running instance.

    This exercises signature checks, routing, and call setup. The call_id is synthetic, so joining
    the call at xAI fails and the conversation is marked as an error: that is expected.
    """
    from voicestack.security.webhooks import sign

    if secret is None:
        from sqlalchemy import select

        from voicestack.db.models import PhoneNumber
        from voicestack.db.session import session_scope
        from voicestack.security.crypto import decrypt

        async def load() -> str | None:
            async with session_scope() as db:
                row = (await db.execute(select(PhoneNumber).where(PhoneNumber.e164 == to))).scalar_one_or_none()
                return decrypt(row.signing_secret_cipher) if row and row.signing_secret_cipher else None

        secret = asyncio.run(load())
        if not secret:
            raise typer.BadParameter(f"No stored signing secret for {to}; pass --secret")
    payload = {
        "object": "event",
        "id": f"evt_{secrets.token_hex(6)}",
        "type": "realtime.call.incoming",
        "created_at": int(time.time()),
        "data": {
            "call_id": call_id or f"sim-{secrets.token_hex(8)}",
            "sip_headers": [{"name": "From", "value": caller}, {"name": "To", "value": to}],
            "metadata": {},
        },
    }
    body = json.dumps(payload).encode()
    msg_id, ts = f"msg_{secrets.token_hex(8)}", int(time.time())
    headers = {
        "webhook-id": msg_id,
        "webhook-timestamp": str(ts),
        "webhook-signature": sign(secret, msg_id, ts, body),
        "content-type": "application/json",
    }
    r = httpx.post(f"{url.rstrip('/')}/webhooks/xai/call-incoming", content=body, headers=headers, timeout=15)
    typer.echo(f"{r.status_code} {r.text}")


@app.command()
def deploy(
    target: Annotated[str, typer.Argument(help="compose | cloudrun | k8s")],
    dry_run: bool = typer.Option(False, help="Print the commands without running them"),
) -> None:
    """Run the deployment script for a target (see docs/deploy/)."""
    scripts = {
        "compose": PROJECT_ROOT / "deploy" / "compose" / "up.sh",
        "cloudrun": PROJECT_ROOT / "deploy" / "cloudrun" / "deploy.sh",
        "k8s": PROJECT_ROOT / "deploy" / "k8s" / "apply.sh",
    }
    script = scripts.get(target)
    if not script or not script.exists():
        raise typer.BadParameter(f"Unknown target {target!r}. Choose: {', '.join(scripts)}")
    env = {**os.environ, "DRY_RUN": "1" if dry_run else "0"}
    raise typer.Exit(subprocess.call(["bash", str(script)], env=env, cwd=PROJECT_ROOT, stdout=sys.stdout, stderr=sys.stderr))


if __name__ == "__main__":
    app()
