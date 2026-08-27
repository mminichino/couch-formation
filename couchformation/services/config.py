from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from couchformation.config import (
    get_project_config_db,
    get_project_resources_db,
    get_project_state_db,
    get_project_uuid_dir,
    get_root_dir,
)
from couchformation.exception import FatalError
from couchformation.identity.id import UniqueId
from couchformation.kvdb import KeyValueStore
from couchformation.models.project import (
    GroupCreateRequest,
    NodeGroupConfig,
    ProjectConfig,
    ProjectCreateRequest,
    ResourceConfig,
    ResourceCreateRequest,
)
from couchformation.util import FileManager, PasswordUtility

logger = logging.getLogger("couchformation.services.config")
logger.addHandler(logging.NullHandler())

INDEX_DB = "projects.db"


class ProjectConfigError(FatalError):
    pass


class ProjectConfigService:
    def __init__(self):
        try:
            if not os.path.exists(get_root_dir()):
                FileManager().make_dir(get_root_dir())
        except Exception as err:
            raise ProjectConfigError(f"can not create root dir: {err}")
        self.index = KeyValueStore(os.path.join(get_root_dir(), INDEX_DB), "projects")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not bool(re.match(r"^[a-z]([-a-z0-9]*[a-z0-9])?$", name)) or len(name) > 63:
            raise ProjectConfigError(f"Invalid name (RFC1035): {name}")

    def create_project(self, request: ProjectCreateRequest) -> ProjectConfig:
        self._validate_name(request.name)
        existing = self.find_by_name(request.name)
        if existing:
            raise ProjectConfigError(f"Project {request.name} already exists")

        uid = UniqueId()
        project_uuid = uid.uuid
        password = request.password or PasswordUtility().generate(16)

        project_dir = get_project_uuid_dir(project_uuid)
        FileManager().make_dir(project_dir)

        config_db = KeyValueStore(get_project_config_db(project_uuid), "config")
        config_db["name"] = request.name
        config_db["uuid"] = project_uuid
        config_db["region"] = request.region
        config_db["cloud"] = request.cloud
        config_db["password"] = password

        self.index[request.name] = project_uuid
        self.index[project_uuid] = request.name

        resources_db = KeyValueStore(get_project_resources_db(project_uuid), "meta")
        resources_db["initialized"] = True

        KeyValueStore(get_project_state_db(project_uuid), "meta")["initialized"] = True

        logger.info(f"Created project {request.name} ({project_uuid})")
        return ProjectConfig(
            name=request.name,
            uuid=project_uuid,
            region=request.region,
            cloud=request.cloud,
            password=password,
        )

    def delete_project(self, name_or_uuid: str) -> None:
        project = self.resolve(name_or_uuid)
        project_dir = get_project_uuid_dir(project.uuid)
        if project.name in self.index:
            del self.index[project.name]
        if project.uuid in self.index:
            del self.index[project.uuid]
        if os.path.exists(project_dir):
            FileManager().remove_tree(project_dir)
        logger.info(f"Deleted project {project.name}")

    def resolve(self, name_or_uuid: str) -> ProjectConfig:
        by_name = self.find_by_name(name_or_uuid)
        if by_name:
            return by_name
        by_uuid = self.find_by_uuid(name_or_uuid)
        if by_uuid:
            return by_uuid
        raise ProjectConfigError(f"Project {name_or_uuid} not found")

    def find_by_name(self, name: str) -> Optional[ProjectConfig]:
        project_uuid = self.index.get(name)
        if not project_uuid:
            return None
        return self.find_by_uuid(project_uuid)

    def find_by_uuid(self, project_uuid: str) -> Optional[ProjectConfig]:
        config_path = get_project_config_db(project_uuid)
        if not os.path.exists(config_path):
            return None
        config_db = KeyValueStore(config_path, "config")
        if not config_db.get("uuid"):
            return None
        return ProjectConfig(
            name=config_db.get("name"),
            uuid=config_db.get("uuid"),
            region=config_db.get("region"),
            cloud=config_db.get("cloud"),
            password=config_db.get("password"),
        )

    def list_projects(self) -> list[ProjectConfig]:
        projects = []
        seen = set()
        for key in list(self.index.keys()):
            value = self.index.get(key)
            if not value or value in seen:
                continue
            # index stores name->uuid and uuid->name
            project = self.find_by_uuid(value) or self.find_by_uuid(key)
            if project and project.uuid not in seen:
                seen.add(project.uuid)
                projects.append(project)
        return projects

    def ensure_password(self, project: ProjectConfig, password: Optional[str] = None) -> str:
        config_db = KeyValueStore(get_project_config_db(project.uuid), "config")
        if password:
            config_db["password"] = password
            return password
        if config_db.get("password"):
            return config_db.get("password")
        generated = PasswordUtility().generate(16)
        config_db["password"] = generated
        return generated

    def create_group(self, name_or_uuid: str, request: GroupCreateRequest) -> NodeGroupConfig:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "groups")
        existing = [k for k in resources.keys() if str(k).startswith("instance.")]
        group_numbers = sorted({int(k.split(".")[1]) for k in existing if len(k.split(".")) > 1 and k.split(".")[1].isdigit()})
        group_number = (max(group_numbers) + 1) if group_numbers else 0

        name = request.name or f"group-{group_number}"
        self._validate_name(name)

        finalizer_group = None
        if request.finalizer:
            finalizer_group = self._next_finalizer_group(project.uuid)

        data = request.model_dump(exclude_none=True)
        data.pop("extra", None)
        data["group"] = group_number
        data["name"] = name
        data["finalizer_group"] = finalizer_group
        data["cloud"] = request.cloud or project.cloud or "aws"
        data["region"] = request.region or project.region

        for key, value in data.items():
            if key == "variables":
                resources[f"instance.{group_number}.variables"] = json.dumps(value)
            else:
                resources[f"instance.{group_number}.{key}"] = value if not isinstance(value, (dict, list)) else json.dumps(value)

        if project.region is None and data.get("region"):
            config_db = KeyValueStore(get_project_config_db(project.uuid), "config")
            config_db["region"] = data["region"]
        if project.cloud is None and data.get("cloud"):
            config_db = KeyValueStore(get_project_config_db(project.uuid), "config")
            config_db["cloud"] = data["cloud"]

        return self.get_group(project.uuid, group_number)

    def _next_finalizer_group(self, project_uuid: str) -> int:
        groups = self.list_groups(project_uuid)
        assigned = [g.finalizer_group for g in groups if g.finalizer_group is not None]
        return (max(assigned) + 1) if assigned else 0

    def remove_group(self, name_or_uuid: str, group_number: int) -> None:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "groups")
        prefix = f"instance.{group_number}."
        for key in list(resources.keys()):
            if str(key).startswith(prefix):
                del resources[key]

    def set_group(self, name_or_uuid: str, group_number: int, updates: dict) -> NodeGroupConfig:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "groups")
        prefix = f"instance.{group_number}."
        if not any(str(k).startswith(prefix) for k in resources.keys()):
            raise ProjectConfigError(f"Group {group_number} not found")
        if updates.get("finalizer") and self.get_group(project.uuid, group_number).finalizer_group is None:
            updates["finalizer_group"] = self._next_finalizer_group(project.uuid)
        for key, value in updates.items():
            if value is None:
                continue
            if key == "variables":
                resources[f"{prefix}variables"] = json.dumps(value)
            else:
                resources[f"{prefix}{key}"] = value if not isinstance(value, (dict, list)) else json.dumps(value)
        return self.get_group(project.uuid, group_number)

    def get_group(self, name_or_uuid: str, group_number: int) -> NodeGroupConfig:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "groups")
        prefix = f"instance.{group_number}."
        data: dict = {"group": group_number, "variables": {}, "parameters": {}}
        found = False
        for key in resources.keys():
            key = str(key)
            if not key.startswith(prefix):
                continue
            found = True
            field = key[len(prefix):]
            value = resources.get(key)
            if field == "variables":
                data["variables"] = json.loads(value) if isinstance(value, str) else (value or {})
            elif field in NodeGroupConfig.model_fields:
                data[field] = value
            else:
                data["parameters"][field] = value
        if not found:
            raise ProjectConfigError(f"Group {group_number} not found")
        if "name" not in data:
            data["name"] = f"group-{group_number}"
        if "cloud" not in data:
            data["cloud"] = project.cloud or "aws"
        return NodeGroupConfig.model_validate(data)

    def list_groups(self, name_or_uuid: str) -> list[NodeGroupConfig]:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "groups")
        numbers = sorted({
            int(k.split(".")[1])
            for k in resources.keys()
            if str(k).startswith("instance.") and len(str(k).split(".")) > 1 and str(k).split(".")[1].isdigit()
        })
        return [self.get_group(project.uuid, n) for n in numbers]

    def create_resource(self, name_or_uuid: str, request: ResourceCreateRequest) -> ResourceConfig:
        project = self.resolve(name_or_uuid)
        self._validate_name(request.name)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "resources")
        if resources.get(f"resource.{request.name}.name"):
            raise ProjectConfigError(f"Resource {request.name} already exists")
        data = request.model_dump(exclude_none=True)
        data.pop("parameters", None)
        for key, value in data.items():
            resources[f"resource.{request.name}.{key}"] = value if not isinstance(value, (dict, list)) else json.dumps(value)
        for key, value in request.parameters.items():
            resources[f"resource.{request.name}.{key}"] = value
        return self.get_resource(project.uuid, request.name)

    def remove_resource(self, name_or_uuid: str, resource_name: str) -> None:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "resources")
        prefix = f"resource.{resource_name}."
        for key in list(resources.keys()):
            if str(key).startswith(prefix):
                del resources[key]

    def set_resource(self, name_or_uuid: str, resource_name: str, updates: dict) -> ResourceConfig:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "resources")
        prefix = f"resource.{resource_name}."
        if not any(str(k).startswith(prefix) for k in resources.keys()):
            raise ProjectConfigError(f"Resource {resource_name} not found")
        for key, value in updates.items():
            if value is None:
                continue
            resources[f"{prefix}{key}"] = value if not isinstance(value, (dict, list)) else json.dumps(value)
        return self.get_resource(project.uuid, resource_name)

    def get_resource(self, name_or_uuid: str, resource_name: str) -> ResourceConfig:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "resources")
        prefix = f"resource.{resource_name}."
        data: dict = {"name": resource_name, "parameters": {}}
        found = False
        for key in resources.keys():
            key = str(key)
            if not key.startswith(prefix):
                continue
            found = True
            field = key[len(prefix):]
            value = resources.get(key)
            if field in ResourceConfig.model_fields and field != "parameters":
                data[field] = value
            else:
                data["parameters"][field] = value
        if not found:
            raise ProjectConfigError(f"Resource {resource_name} not found")
        if "cloud" not in data:
            data["cloud"] = "capella"
        return ResourceConfig.model_validate(data)

    def list_resources(self, name_or_uuid: str) -> list[ResourceConfig]:
        project = self.resolve(name_or_uuid)
        resources = KeyValueStore(get_project_resources_db(project.uuid), "resources")
        names = sorted({
            str(k).split(".")[1]
            for k in resources.keys()
            if str(k).startswith("resource.") and len(str(k).split(".")) > 1
        })
        return [self.get_resource(project.uuid, name) for name in names]
