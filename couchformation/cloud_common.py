from __future__ import annotations

from typing import Any

from couchformation.deployment import MetadataManager
from couchformation.naming import ResourceName, project_tag, tags_to_csv
from couchformation.resources.config_manager import ConfigurationManager


def resolve_project_uuid(parameters: dict) -> str:
    if parameters.get("project_uuid"):
        return parameters["project_uuid"]
    project = parameters.get("project")
    if project:
        uid = MetadataManager(project).project_uid
        if uid:
            return uid
    return ResourceName.new_project_id().uuid


def asset_names(project_uuid: str) -> dict[str, str]:
    hex_id = ResourceName.hex_from_uuid(project_uuid)
    return {
        "hex_id": hex_id,
        "asset_prefix": f"cf-{hex_id}",
        "vpc_name": ResourceName.build("vpc", project_uuid, 1),
        "subnet_name": ResourceName.build("subnet", project_uuid, 1),
        "sg_name": ResourceName.build("sg", project_uuid, 1),
        "ig_name": ResourceName.build("igw", project_uuid, 1),
        "rt_name": ResourceName.build("rt", project_uuid, 1),
        "key_name": ResourceName.build("key", project_uuid, 1),
        "rg_name": ResourceName.build("rg", project_uuid, 1),
        "nsg_name": ResourceName.build("nsg", project_uuid, 1),
        "fw_default": ResourceName.build("fw", project_uuid, 1),
        "fw_ssh": ResourceName.build("fw", project_uuid, 2),
        "fw_win": ResourceName.build("fw", project_uuid, 3),
        "dns_link": ResourceName.build("dnslink", project_uuid, 1),
    }


def merge_project_tags(parameters: dict, project_uuid: str, project_name: str | None = None) -> str:
    tags = parameters.get("tags")
    cm = ConfigurationManager()
    cloud = (parameters.get("cloud") or "").lower()
    if not tags and cloud:
        tags = cm.get(f"{cloud}.tags") or cm.get("tags")
    base = project_tag(project_uuid)
    if project_name:
        base["Project"] = project_name
    return tags_to_csv(base, tags)


def state_to_dict(state: Any) -> dict:
    if hasattr(state, "as_dict"):
        return dict(state.as_dict)
    if isinstance(state, dict):
        return dict(state)
    return {}
