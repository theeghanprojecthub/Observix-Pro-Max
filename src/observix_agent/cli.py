from __future__ import annotations

import typer

from observix_common.config import load_yaml
from observix_agent.agent import Agent

app = typer.Typer(help="Observix Agent CLI")


@app.command("run")
def run(
    config: str = typer.Option(..., "--config", "-c"),
) -> None:
    cfg = load_yaml(config)

    agent = Agent(
        agent_id=str(cfg["agent_id"]),
        region=str(cfg["region"]),
        tenant_id=cfg.get("tenant_id"),
        admin_port=cfg.get("admin_port"),
        control_plane_url=str(cfg["control_plane_url"]),
        poll_assignments_seconds=int(cfg.get("poll_assignments_seconds", 3)),
        state_dir=str(cfg.get("state_dir", f"state/{cfg['agent_id']}")),
    )
    agent.run_forever()


if __name__ == "__main__":
    app()
