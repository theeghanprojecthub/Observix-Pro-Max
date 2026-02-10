from __future__ import annotations

import typer
import uvicorn

from observix_common.config import load_yaml
from observix_control_plane.api import Settings, create_app
from observix_control_plane.db import init_engine

app = typer.Typer(help="Observix Control Plane CLI")


@app.command("run")
def run(
    config: str = typer.Option("config/control_plane.yaml", "--config", "-c"),
) -> None:
    cfg = load_yaml(config)
    settings = Settings(**cfg)

    init_engine(settings.database_url)

    api = create_app(settings)
    uvicorn.run(api, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    app()
