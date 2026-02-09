from __future__ import annotations

import shutil
from pathlib import Path
from .control_plane import cp_app
from .agent import agent_app
from .indexer import indexer_app

import typer

app = typer.Typer(
    help="Observix CLI: manage control-plane, agents, pipelines and indexer.",
    invoke_without_command=True,  # force group mode
    no_args_is_help=True,
)

app.add_typer(cp_app, name="cp")
app.add_typer(agent_app, name="agent")
app.add_typer(indexer_app, name="indexer")


TEMPLATES_DIR = Path(__file__).parent / "config_templates"


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        typer.echo(f"skip: {dst} already exists")
        return
    shutil.copy2(src, dst)
    typer.echo(f"created: {dst}")


@app.callback()
def main() -> None:
    """
    Root command for Observix CLI.

    If you run `observix` with no subcommand, help is shown.
    """
    return


@app.command("init")
def init_cmd(
    path: Path = typer.Option(
        Path("config"), "--path", "-p", help="Output config folder"
    ),
) -> None:
    """
    Create a starter config folder with example YAMLs and a demo pipeline spec.
    """
    if not TEMPLATES_DIR.exists():
        raise typer.BadParameter(
            f"Templates folder missing in package: {TEMPLATES_DIR}"
        )

    _copy_file(TEMPLATES_DIR / "agent.example.yaml", path / "agent.example.yaml")
    _copy_file(
        TEMPLATES_DIR / "control_plane.example.yaml",
        path / "control_plane.example.yaml",
    )
    _copy_file(TEMPLATES_DIR / "indexer.example.yaml", path / "indexer.example.yaml")

    _copy_file(
        TEMPLATES_DIR / "pipelines" / "demo-file-tail-to-http.json",
        path / "pipelines" / "demo-file-tail-to-http.json",
    )

    typer.echo("\nDone. Next:")
    typer.echo("  observix-control-plane -c config/control_plane.example.yaml")
    typer.echo("  observix-agent -c config/agent.example.yaml")
