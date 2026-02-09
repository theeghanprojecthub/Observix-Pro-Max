from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import typer

cp_app = typer.Typer(help="Control-plane operations (no curl needed).")


def _cp_url(url: Optional[str]) -> str:
    return (url or os.getenv("OBSERVIX_CP_URL") or "http://127.0.0.1:7000").rstrip("/")


def _print_json(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, sort_keys=False, default=str))


def _read_json_file(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise typer.BadParameter(f"Spec file not found: {path}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON in {path}: {e}")


def _request(
    method: str,
    base: str,
    endpoint: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
) -> Any:
    url = f"{base}{endpoint}"
    with httpx.Client(timeout=timeout) as client:
        r = client.request(method, url, json=json_body)
        r.raise_for_status()

        # Some endpoints might return empty body, handle safely
        if not r.text.strip():
            return {"ok": True}

        # Prefer JSON if possible
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}


@cp_app.command("health")
def health(
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL")
) -> None:
    """
    Check control-plane healthz.
    """
    base = _cp_url(url)
    out = _request("GET", base, "/healthz", timeout=5.0)
    _print_json(out)


@cp_app.command("agents")
def agents_list(
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL")
) -> None:
    """
    List registered agents.
    """
    base = _cp_url(url)
    out = _request("GET", base, "/v1/agents")
    _print_json(out)


# -------------------------
# Pipelines group
# -------------------------
pipelines_app = typer.Typer(help="Pipeline operations.")
cp_app.add_typer(pipelines_app, name="pipelines")


@pipelines_app.command("list")
def pipelines_list(
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL")
) -> None:
    """
    List pipelines.
    """
    base = _cp_url(url)
    out = _request("GET", base, "/v1/pipelines")
    _print_json(out)


@pipelines_app.command("create")
def pipelines_create(
    name: str = typer.Option(..., "--name", help="Pipeline name"),
    spec_file: Path = typer.Option(
        ...,
        "--spec-file",
        "-f",
        exists=False,
        help="JSON file containing pipeline spec",
    ),
    enabled: bool = typer.Option(
        True, "--enabled/--disabled", help="Whether pipeline is enabled"
    ),
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL"),
) -> None:
    """
    Create a pipeline from a JSON spec file.
    Spec file should contain: source, processor(optional), destination, batch_* (optional)
    """
    base = _cp_url(url)
    spec = _read_json_file(spec_file)

    body = {"name": name, "enabled": enabled, "spec": spec}
    out = _request("POST", base, "/v1/pipelines", json_body=body, timeout=15.0)
    _print_json(out)


@pipelines_app.command("update")
def pipelines_update(
    pipeline_id: str = typer.Option(..., "--pipeline-id", help="Pipeline ID to update"),
    name: str = typer.Option(..., "--name", help="Pipeline name"),
    spec_file: Path = typer.Option(
        ...,
        "--spec-file",
        "-f",
        exists=False,
        help="JSON file containing pipeline spec",
    ),
    enabled: bool = typer.Option(
        True, "--enabled/--disabled", help="Whether pipeline is enabled"
    ),
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL"),
) -> None:
    """
    Update an existing pipeline.
    """
    base = _cp_url(url)
    spec = _read_json_file(spec_file)

    body = {"name": name, "enabled": enabled, "spec": spec}
    out = _request(
        "PUT", base, f"/v1/pipelines/{pipeline_id}", json_body=body, timeout=15.0
    )
    _print_json(out)


@pipelines_app.command("rename")
def pipelines_rename(
    pipeline_id: str = typer.Option(..., "--pipeline-id", help="Pipeline ID to rename"),
    name: str = typer.Option(..., "--name", help="New pipeline name"),
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL"),
) -> None:
    base = _cp_url(url)
    body = {"name": name}
    out = _request(
        "PATCH", base, f"/v1/pipelines/{pipeline_id}", json_body=body, timeout=15.0
    )
    _print_json(out)


# -------------------------
# Assignments group
# -------------------------
assignments_app = typer.Typer(help="Assignment operations.")
cp_app.add_typer(assignments_app, name="assignments")


@assignments_app.command("get")
def assignments_get(
    agent_id: str = typer.Option(..., "--agent-id", help="Agent ID"),
    region: str = typer.Option(..., "--region", help="Agent region"),
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL"),
) -> None:
    """
    Get assignments for an agent in a region.
    """
    base = _cp_url(url)
    out = _request(
        "GET", base, f"/v1/agents/{agent_id}/assignments?region={region}", timeout=15.0
    )
    _print_json(out)


@assignments_app.command("create")
def assignments_create(
    agent_id: str = typer.Option(..., "--agent-id", help="Agent ID"),
    region: str = typer.Option(..., "--region", help="Region"),
    pipeline_id: str = typer.Option(..., "--pipeline-id", help="Pipeline ID"),
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL"),
) -> None:
    """
    Create an assignment (bind pipeline to an agent/region).
    """
    base = _cp_url(url)
    body = {"agent_id": agent_id, "region": region, "pipeline_id": pipeline_id}
    out = _request("POST", base, "/v1/assignments", json_body=body, timeout=15.0)
    _print_json(out)


@assignments_app.command("delete")
def assignments_delete(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    url: Optional[str] = typer.Option(None, "--url", help="Control plane base URL"),
) -> None:
    """
    Delete an assignment by ID.
    """
    base = _cp_url(url)
    out = _request("DELETE", base, f"/v1/assignments/{assignment_id}", timeout=15.0)
    _print_json(out)
