from __future__ import annotations

import typer
import uvicorn

from observix_common.config import load_yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7100
    allow_origins: list[str] = Field(default_factory=lambda: ["*"])


app = typer.Typer(help="Observix Indexer CLI")


@app.command("run")
def run(
    config: str = typer.Option("config/indexer.example.yaml", "--config", "-c"),
) -> None:
    """
    Run the Observix Indexer API server.
    """
    cfg = load_yaml(config) or {}
    settings = Settings(**cfg)

    # IMPORTANT: pass uvicorn an import string, not the app object
    uvicorn.run(
        "observix_indexer.api:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    app()
