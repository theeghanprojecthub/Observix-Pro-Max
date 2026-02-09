from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import typer
import yaml

agent_app = typer.Typer(help="Agent operations (local + admin APIs).")


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise typer.BadParameter(f"Config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _agent_admin_url(url: Optional[str]) -> str:
    # Allow explicit override first
    if url:
        return url.rstrip("/")

    # Env override
    env = os.getenv("OBSERVIX_AGENT_ADMIN_URL")
    if env:
        return env.rstrip("/")

    # If nothing, default
    return "http://127.0.0.1:7301"


def _print(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@agent_app.command("ping")
def ping(
    url: Optional[str] = typer.Option(None, "--url", help="Agent admin base URL")
) -> None:
    """
    Ping agent admin API (if you expose it).
    """
    base = _agent_admin_url(url)
    r = httpx.get(f"{base}/healthz", timeout=5.0)
    r.raise_for_status()
    try:
        _print(r.json())
    except Exception:
        typer.echo(r.text)


@agent_app.command("udp-send")
def udp_send(
    host: str = typer.Option(..., "--host", help="Destination host"),
    port: int = typer.Option(..., "--port", help="Destination UDP port"),
    message: str = typer.Option(..., "--message", "-m", help="Message to send"),
    count: int = typer.Option(1, "--count", "-n", help="How many messages"),
    interval: float = typer.Option(0.2, "--interval", help="Seconds between sends"),
) -> None:
    """
    Quick UDP sender to test syslog destinations / listeners.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent = 0
    for i in range(count):
        sock.sendto(message.encode("utf-8"), (host, port))
        sent += 1
        time.sleep(interval)
    sock.close()
    typer.echo(f"sent={sent} -> {host}:{port}")


@agent_app.command("validate-config")
def validate_config(
    config: Path = typer.Option(..., "--config", "-c", help="Agent YAML config file"),
) -> None:
    """
    Validate agent config YAML is parseable and includes required keys.
    (This is lightweight validation, not full schema.)
    """
    cfg = _read_yaml(config)

    required = ["agent_id", "region", "control_plane_url"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise typer.BadParameter(f"Missing required fields: {', '.join(missing)}")

    typer.echo("ok: config parsed and required fields present")
