"""libby CLI entry point."""

import typer

app = typer.Typer(
    name="libby",
    help="AI-friendly CLI tool for scholarly paper management",
    add_completion=False,
    no_args_is_help=True,
)


def version_callback(value: bool):
    """Callback for version option."""
    if value:
        from libby import __version__
        typer.echo(f"libby version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """libby - Scholarly paper management CLI."""


# 子命令将在后续任务中注册
# app.add_typer(extract_app, name="extract")


if __name__ == "__main__":
    app()