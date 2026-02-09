from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx
import typer

indexer_app = typer.Typer(help="Indexer operations (health, profiles, test parsing).")


def _indexer_url(url: Optional[str]) -> str:
    return (url or os.getenv("OBSERVIX_INDEXER_URL") or "http://127.0.0.1:7100").rstrip(
        "/"
    )


def _print(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


@indexer_app.command("health")
def health(
    url: Optional[str] = typer.Option(None, "--url", help="Indexer base URL")
) -> None:
    """
    Check indexer health.
    """
    base = _indexer_url(url)
    r = httpx.get(f"{base}/healthz", timeout=5.0)
    r.raise_for_status()
    try:
        _print(r.json())
    except Exception:
        typer.echo(r.text)


@indexer_app.command("profiles")
def profiles(
    url: Optional[str] = typer.Option(None, "--url", help="Indexer base URL")
) -> None:
    """
    List available indexer profiles.
    """
    base = _indexer_url(url)
    r = httpx.get(f"{base}/v1/profiles", timeout=10.0)
    r.raise_for_status()
    try:
        _print(r.json())
    except Exception:
        typer.echo(r.text)


@indexer_app.command("profile")
def profile_show(
    name: str = typer.Argument(..., help="Profile name"),
    url: Optional[str] = typer.Option(None, "--url", help="Indexer base URL"),
) -> None:
    """
    Show a profile definition.
    """
    base = _indexer_url(url)
    r = httpx.get(f"{base}/v1/profiles/{name}", timeout=10.0)
    r.raise_for_status()
    try:
        _print(r.json())
    except Exception:
        typer.echo(r.text)


@indexer_app.command("test")
def test_parse(
    profile: str = typer.Option(
        "passthrough", "--profile", "-p", help="Profile to use"
    ),
    text: str = typer.Option(..., "--text", "-t", help="Raw log line to parse"),
    url: Optional[str] = typer.Option(None, "--url", help="Indexer base URL"),
) -> None:
    """
    Send one raw log line to indexer and print structured result.
    """
    base = _indexer_url(url)
    payload = {"profile": profile, "text": text}

    r = httpx.post(f"{base}/v1/index", json=payload, timeout=10.0)
    r.raise_for_status()
    try:
        _print(r.json())
    except Exception:
        typer.echo(r.text)
