from __future__ import annotations

import json
import logging
import warnings
from typing import Optional

import typer

import couchformation
from couchformation.models.project import (
    GroupCreateRequest,
    PeerConfigRequest,
    ProjectCreateRequest,
    ResourceCreateRequest,
)
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService
from couchformation.services.importer import ProjectImportService
from couchformation.ssh import SSHUtil

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("cloudmgr")

app = typer.Typer(help="Couch Formation cloud manager", no_args_is_help=True)
config_app = typer.Typer(help="Configuration manager")
create_app = typer.Typer(help="Create resources")
delete_app = typer.Typer(help="Delete resources")
list_app = typer.Typer(help="List resources")
project_app = typer.Typer(help="Project operations", invoke_without_command=False)
project_create_app = typer.Typer(help="Create project resources")
project_remove_app = typer.Typer(help="Remove project resources")
project_set_app = typer.Typer(help="Update project resources")
ssh_app = typer.Typer(help="SSH key manager")

app.add_typer(config_app, name="config")
app.add_typer(create_app, name="create")
app.add_typer(delete_app, name="delete")
app.add_typer(list_app, name="list")
app.add_typer(project_app, name="project")
app.add_typer(ssh_app, name="ssh")
project_app.add_typer(project_create_app, name="create")
project_app.add_typer(project_remove_app, name="remove")
project_app.add_typer(project_set_app, name="set")


def _parse_variables(values: Optional[list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid variable '{item}', expected key=value")
        key, value = item.split("=", 1)
        result[key] = value
    return result


@app.callback()
def main_callback(
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
):
    if version:
        typer.echo(f"Couch Formation v{couchformation.__version__}")
        raise typer.Exit()


@app.command("init")
def init_cmd(
    api_token: Optional[str] = typer.Option(None, "--api-token", help="API JWT secret/token"),
):
    """Initialize global configuration."""
    cm = ConfigurationManager()
    token = cm.ensure_api_token(api_token)
    typer.echo(f"Initialized config at {cm.filename}")
    typer.echo(f"API token ready ({token[:4]}...)")


@config_app.command("get")
def config_get(key: Optional[str] = typer.Argument(None)):
    cm = ConfigurationManager()
    if key is None:
        for k, v in cm.list().items():
            typer.echo(f"{k} = {v}")
        return
    value = cm.get(key)
    if value is not None:
        typer.echo(f"{key} = {value}")


@config_app.command("set")
def config_set(key: str, value: str):
    ConfigurationManager().set(key, value)
    typer.echo(f"Set {key}")


@config_app.command("unset")
def config_unset(key: str):
    ConfigurationManager().delete(key)
    typer.echo(f"Unset {key}")


@create_app.command("project")
def create_project(
    name: str = typer.Argument(...),
    region: Optional[str] = typer.Option(None, "--region"),
    cloud: Optional[str] = typer.Option("aws", "--cloud"),
    password: Optional[str] = typer.Option(None, "--password"),
):
    project = ProjectConfigService().create_project(
        ProjectCreateRequest(name=name, region=region, cloud=cloud, password=password)
    )
    typer.echo(f"Created project {project.name} ({project.uuid})")


@delete_app.command("project")
def delete_project(name: str = typer.Argument(...)):
    ProjectConfigService().delete_project(name)
    typer.echo(f"Deleted project {name}")


@list_app.command("projects")
def list_projects():
    for project in ProjectConfigService().list_projects():
        typer.echo(f"{project.name}\t{project.uuid}\t{project.cloud or '-'}\t{project.region or '-'}")


@list_app.command("resources")
def list_resources(project_name: str = typer.Argument(...)):
    svc = ProjectConfigService()
    for group in svc.list_groups(project_name):
        typer.echo(f"group\t{group.group}\t{group.name}\t{group.cloud}\tcount={group.count}")
    for resource in svc.list_resources(project_name):
        typer.echo(f"resource\t{resource.name}\t{resource.cloud}")


@project_app.callback()
def project_callback(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Project name or UUID"),
):
    ctx.ensure_object(dict)
    ctx.obj["project"] = name


@project_create_app.command("group")
def project_create_group(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name"),
    cloud: str = typer.Option("aws", "--cloud"),
    region: Optional[str] = typer.Option(None, "--region"),
    count: int = typer.Option(1, "--count"),
    availability_zone: Optional[str] = typer.Option(None, "--availability-zone"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    build: str = typer.Option("cbs", "--build"),
    os_id: str = typer.Option("ubuntu", "--os-id"),
    os_version: str = typer.Option("24.04", "--os-version"),
    machine_type: Optional[str] = typer.Option("4x16", "--machine-type"),
    services: Optional[str] = typer.Option("default", "--services"),
    finalizer: Optional[str] = typer.Option(None, "--finalizer"),
    variable: Optional[list[str]] = typer.Option(None, "--variable", help="key=value (repeatable)"),
):
    project = ctx.obj["project"]
    group = ProjectConfigService().create_group(
        project,
        GroupCreateRequest(
            name=name,
            cloud=cloud,
            region=region,
            count=count,
            availability_zone=availability_zone,
            profile=profile,
            build=build,
            os_id=os_id,
            os_version=os_version,
            machine_type=machine_type,
            services=services,
            finalizer=finalizer,
            variables=_parse_variables(variable),
        ),
    )
    typer.echo(f"Created group {group.group} ({group.name})")


@project_create_app.command("resource")
def project_create_resource(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    cloud: str = typer.Option("capella", "--cloud"),
    region: Optional[str] = typer.Option(None, "--region"),
    provider: Optional[str] = typer.Option("aws", "--provider"),
    quantity: int = typer.Option(1, "--quantity"),
    machine_type: Optional[str] = typer.Option(None, "--machine-type"),
):
    project = ctx.obj["project"]
    resource = ProjectConfigService().create_resource(
        project,
        ResourceCreateRequest(
            name=name,
            cloud=cloud,
            region=region,
            provider=provider,
            quantity=quantity,
            machine_type=machine_type,
        ),
    )
    typer.echo(f"Created resource {resource.name}")


@project_remove_app.command("group")
def project_remove_group(
    ctx: typer.Context,
    group_number: int = typer.Argument(...),
):
    ProjectConfigService().remove_group(ctx.obj["project"], group_number)
    typer.echo(f"Removed group {group_number}")


@project_remove_app.command("resource")
def project_remove_resource(
    ctx: typer.Context,
    resource_name: str = typer.Argument(...),
):
    ProjectConfigService().remove_resource(ctx.obj["project"], resource_name)
    typer.echo(f"Removed resource {resource_name}")


@project_set_app.command("group")
def project_set_group(
    ctx: typer.Context,
    group_number: int = typer.Argument(...),
    count: Optional[int] = typer.Option(None, "--count"),
    machine_type: Optional[str] = typer.Option(None, "--machine-type"),
    finalizer: Optional[str] = typer.Option(None, "--finalizer"),
    variable: Optional[list[str]] = typer.Option(None, "--variable"),
):
    updates = {
        "count": count,
        "machine_type": machine_type,
        "finalizer": finalizer,
    }
    vars_map = _parse_variables(variable)
    if vars_map:
        updates["variables"] = vars_map
    group = ProjectConfigService().set_group(ctx.obj["project"], group_number, updates)
    typer.echo(f"Updated group {group.group}")


@project_set_app.command("resource")
def project_set_resource(
    ctx: typer.Context,
    resource_name: str = typer.Argument(...),
    quantity: Optional[int] = typer.Option(None, "--quantity"),
    machine_type: Optional[str] = typer.Option(None, "--machine-type"),
    region: Optional[str] = typer.Option(None, "--region"),
):
    resource = ProjectConfigService().set_resource(
        ctx.obj["project"],
        resource_name,
        {"quantity": quantity, "machine_type": machine_type, "region": region},
    )
    typer.echo(f"Updated resource {resource.name}")


@project_app.command("deploy")
def project_deploy(ctx: typer.Context):
    result = ProjectDeployService().deploy(ctx.obj["project"])
    typer.echo(json.dumps(result, indent=2, default=str))


@project_app.command("destroy")
def project_destroy(ctx: typer.Context):
    result = ProjectDeployService().destroy(ctx.obj["project"])
    typer.echo(json.dumps(result, indent=2, default=str))


@project_app.command("status")
def project_status(ctx: typer.Context):
    result = ProjectDeployService().status(ctx.obj["project"])
    typer.echo(json.dumps(result, indent=2, default=str))


@project_app.command("import")
def project_import(ctx: typer.Context):
    result = ProjectImportService().import_project(ctx.obj["project"])
    typer.echo(json.dumps(result, indent=2, default=str))


@project_app.command("peer")
def project_peer(
    ctx: typer.Context,
    provider_id: Optional[str] = typer.Option(None, "--provider-id"),
    hosted_zone: Optional[str] = typer.Option(None, "--hosted-zone"),
    peer_project: Optional[str] = typer.Option(None, "--peer-project"),
    peer_region: Optional[str] = typer.Option(None, "--peer-region"),
    cloud: Optional[str] = typer.Option(None, "--cloud"),
    region: Optional[str] = typer.Option(None, "--region"),
):
    result = ProjectDeployService().peer(
        ctx.obj["project"],
        PeerConfigRequest(
            provider_id=provider_id,
            hosted_zone=hosted_zone,
            peer_project=peer_project,
            peer_region=peer_region,
            cloud=cloud,
            region=region,
        ),
    )
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("start")
def start_server(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
):
    """Start the REST API server."""
    import uvicorn
    from couchformation.api.app import create_app

    ConfigurationManager().ensure_api_token()
    uvicorn.run(create_app(), host=host, port=port)


@app.command("stop")
def stop_server():
    """Stop is handled by terminating the start server process."""
    typer.echo("Stop the server process (Ctrl+C) or kill the uvicorn PID.")


@ssh_app.command("create")
def ssh_create(
    name: str = typer.Option("cf-key-pair", "--name", "-n"),
    replace: bool = typer.Option(False, "--replace", "-r"),
):
    _, private_file = SSHUtil.create_key_pair(name, replace)
    ConfigurationManager().set("ssh.key", private_file)
    typer.echo(f"Created SSH key {private_file}")


def main(args=None):
    app(args=args)


if __name__ == "__main__":
    main()
