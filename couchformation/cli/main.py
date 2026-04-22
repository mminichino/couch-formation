##
##

import importlib
import logging
from typing import List, Optional

import typer

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="cloudmgr",
    help="Couch Formation cloud infrastructure manager",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

create_app = typer.Typer(help="Create resources.", no_args_is_help=True)
active_app = typer.Typer(help="Set active resources.", no_args_is_help=True)
show_app = typer.Typer(help="Show resource information.", no_args_is_help=True)
add_app = typer.Typer(help="Add resources.", no_args_is_help=True)
network_app = typer.Typer(help="Manage network settings.", no_args_is_help=True)
delete_app = typer.Typer(help="Delete resources.", no_args_is_help=True)
instance_app = typer.Typer(help="Manage instances.", no_args_is_help=True)

app.add_typer(create_app, name="create")
app.add_typer(active_app, name="active")
app.add_typer(show_app, name="show")
app.add_typer(add_app, name="add")
app.add_typer(network_app, name="network")
app.add_typer(delete_app, name="delete")
app.add_typer(instance_app, name="instance")


@create_app.command("project")
def create_project(
    project_name: str = typer.Argument(..., help="Name of the project to create."),
) -> None:
    """Create a new project."""
    pass


@active_app.command("project")
def active_project(
    project_name: str = typer.Argument(..., help="Name of the project to activate."),
) -> None:
    """Set the active project."""
    pass


@show_app.command("project")
def show_project() -> None:
    """Show the active project."""
    pass


@add_app.command("ssh")
def add_ssh(
    key: Optional[str] = typer.Option(None, "--key", help="Path to an existing SSH public key file."),
) -> None:
    """Add an SSH key to the active project."""
    pass


@network_app.command("config")
def network_config(
    cidr: Optional[str] = typer.Option(None, "--cidr", help="Network CIDR block (e.g. 10.0.0.0/16)."),
    domain: Optional[str] = typer.Option(None, "--domain", help="DNS domain name for the network."),
) -> None:
    """Configure network settings for the active project."""
    pass


@network_app.command("peer")
def network_peer(
    project: Optional[str] = typer.Option(None, "--project", help="Remote project name to peer with."),
) -> None:
    """Configure network peering for the active project."""
    pass


@app.command("cloud")
def cloud(
    name: str = typer.Argument(..., help="Cloud provider name (e.g. aws, gcp, azure)."),
) -> None:
    """Set the cloud provider for the active project."""
    pass


@app.command("region")
def region(
    region: str = typer.Argument(..., help="Cloud region (e.g. us-east-1)."),
) -> None:
    """Set the cloud region for the active project."""
    pass


@add_app.command("instances")
def add_instances(
    group_name: str = typer.Argument(..., help="Instance group name."),
    quantity: Optional[int] = typer.Option(None, "--quantity", help="Number of instances."),
    os: Optional[str] = typer.Option(None, "--os", help="Operating system name."),
    os_version: Optional[str] = typer.Option(None, "--os-version", help="Operating system version."),
    shape: Optional[str] = typer.Option(None, "--shape", help="Instance shape / machine type."),
    root_size: Optional[int] = typer.Option(None, "--root-size", help="Root volume size in GB."),
    data_size: Optional[int] = typer.Option(None, "--data-size", help="Data volume size in GB."),
    tag: Optional[List[str]] = typer.Option(None, "--tag", help="Arbitrary tag (repeatable)."),
) -> None:
    """Add an instance group to the active project."""
    pass


@delete_app.command("instances")
def delete_instances(
    group_name: str = typer.Argument(..., help="Instance group name to delete."),
) -> None:
    """Delete an instance group from the active project."""
    pass


def _load_profile_class(profile_name: str):
    """Import and return the profile class for *profile_name*.

    Profile modules live in couchformation.library and must export a
    class whose name matches the module name with an initial capital letter.
    """
    try:
        module = importlib.import_module(f"couchformation.library.{profile_name}")
    except ModuleNotFoundError:
        typer.echo(f"Error: unknown profile '{profile_name}'.", err=True)
        raise typer.Exit(code=1)

    class_name = profile_name.capitalize()
    cls = getattr(module, class_name, None)
    if cls is None:
        typer.echo(f"Error: profile module '{profile_name}' has no class '{class_name}'.", err=True)
        raise typer.Exit(code=1)

    return cls


@instance_app.command(
    "profile",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def instance_profile(
    ctx: typer.Context,
    group_name: str = typer.Argument(..., help="Instance group name."),
    profile_name: str = typer.Argument(..., help="Profile name (must match a module in couchformation.library)."),
) -> None:
    """Apply a profile to an instance group.

    Profile-specific flags are forwarded to the profile class.  Run
    cloudmgr instance profile <group> <profile> --help once profiles
    expose their own options.
    """
    profile_cls = _load_profile_class(profile_name)
    profile_kwargs = _parse_extra_args(ctx.args)
    profile_cls().apply(group_name, **profile_kwargs)


def _parse_extra_args(args: List[str]) -> dict:
    result: dict = {}
    it = iter(args)
    for token in it:
        if token.startswith("--"):
            key = token.lstrip("-").replace("-", "_")
            try:
                peek = next(it)
                if peek.startswith("--"):
                    result[key] = True
                    # put peek back by processing it in the outer loop
                    result[peek.lstrip("-").replace("-", "_")] = True
                else:
                    result[key] = peek
            except StopIteration:
                result[key] = True
    return result


@app.command("deploy")
def deploy() -> None:
    """Deploy the active project."""
    pass


@app.command("destroy")
def destroy() -> None:
    """Destroy the active project."""
    pass


def main() -> None:
    app()


if __name__ == "__main__":
    main()
