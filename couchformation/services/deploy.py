from __future__ import annotations

import importlib
import json
import logging
from typing import Any, Optional

from couchformation.config import get_project_state_db
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.models.cloud_ops import (
    FoundationRequest,
    NodeRequest,
    PeerRequest,
    ResourceRequest,
)
from couchformation.models.project import NodeGroupConfig, PeerConfigRequest, ProjectConfig
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.services.config import ProjectConfigService

logger = logging.getLogger("couchformation.services.deploy")
logger.addHandler(logging.NullHandler())


class ProjectDeployError(FatalError):
    pass


CLOUD_MODULES = {
    "aws": "couchformation.aws",
    "gcp": "couchformation.gcp",
    "azure": "couchformation.azure",
    "capella": "couchformation.capella",
}


def _load_cloud_class(cloud: str, module_name: str, class_name: str):
    package = CLOUD_MODULES.get(cloud)
    if not package:
        raise ProjectDeployError(f"Unsupported cloud: {cloud}")
    module = importlib.import_module(f"{package}.{module_name}")
    return getattr(module, class_name)()


class ProjectDeployService:
    def __init__(self):
        self.config_service = ProjectConfigService()

    def deploy(self, name_or_uuid: str) -> dict[str, Any]:
        project = self.config_service.resolve(name_or_uuid)
        password = self.config_service.ensure_password(project)
        results: dict[str, Any] = {"project": project.model_dump(), "foundations": [], "nodes": [], "resources": []}

        groups = self.config_service.list_groups(project.uuid)
        resources = self.config_service.list_resources(project.uuid)

        clouds_regions = {(g.cloud, g.region or project.region) for g in groups if g.cloud != "capella"}
        for cloud, region in clouds_regions:
            if not region:
                raise ProjectDeployError(f"Region required for cloud {cloud}")
            foundation_result = self._deploy_foundation(project, cloud, region)
            results["foundations"].append(foundation_result.model_dump())

        for group in groups:
            if group.cloud == "capella":
                continue
            node_results = self._deploy_group_nodes(project, group, password)
            results["nodes"].extend([n.model_dump() for n in node_results])
            self._run_finalizers(project, group, node_results, password)

        for resource in resources:
            resource_result = self._deploy_resource(project, resource, password)
            results["resources"].append(resource_result.model_dump())

        return results

    def destroy(self, name_or_uuid: str) -> dict[str, Any]:
        project = self.config_service.resolve(name_or_uuid)
        results: dict[str, Any] = {"project": project.model_dump(), "destroyed": []}

        for resource in reversed(self.config_service.list_resources(project.uuid)):
            module = _load_cloud_class(resource.cloud, "resource", "Resource")
            req = ResourceRequest(
                project=project.name,
                project_uuid=project.uuid,
                cloud=resource.cloud,
                name=resource.name,
                region=resource.region or project.region,
                **{k: v for k, v in resource.model_dump().items() if k not in {"name", "cloud", "region", "parameters"}},
            )
            module.destroy(req)
            results["destroyed"].append({"type": "resource", "name": resource.name})

        for group in reversed(self.config_service.list_groups(project.uuid)):
            if group.cloud == "capella":
                continue
            for number in range(1, (group.count or 1) + 1):
                module = _load_cloud_class(group.cloud, "node", "Node")
                req = NodeRequest(
                    project=project.name,
                    project_uuid=project.uuid,
                    cloud=group.cloud,
                    region=group.region or project.region,
                    name=group.name,
                    group=group.group,
                    number=number,
                )
                module.destroy(req)
                results["destroyed"].append({"type": "node", "name": group.name, "number": number})

        clouds_regions = {
            (g.cloud, g.region or project.region)
            for g in self.config_service.list_groups(project.uuid)
            if g.cloud != "capella"
        }
        for cloud, region in clouds_regions:
            module = _load_cloud_class(cloud, "foundation", "Foundation")
            req = FoundationRequest(
                project=project.name,
                project_uuid=project.uuid,
                cloud=cloud,
                region=region,
            )
            module.destroy(req)
            results["destroyed"].append({"type": "foundation", "cloud": cloud, "region": region})

        return results

    def peer(self, name_or_uuid: str, request: PeerConfigRequest) -> dict[str, Any]:
        project = self.config_service.resolve(name_or_uuid)
        cloud = request.cloud or project.cloud
        region = request.region or project.region
        if not cloud or not region:
            raise ProjectDeployError("cloud and region are required for peering")
        module = _load_cloud_class(cloud, "peer", "Peer")
        peer_req = PeerRequest(
            project=project.name,
            project_uuid=project.uuid,
            cloud=cloud,
            region=region,
            provider_id=request.provider_id,
            hosted_zone=request.hosted_zone,
            peer_project=request.peer_project,
            peer_region=request.peer_region,
        )
        result = module.create(peer_req)
        self._save_state(project.uuid, f"peer:{cloud}:{region}", result.model_dump())
        return result.model_dump()

    def status(self, name_or_uuid: str) -> dict[str, Any]:
        project = self.config_service.resolve(name_or_uuid)
        state_db = KeyValueStore(get_project_state_db(project.uuid), "meta")
        return {
            "project": project.model_dump(exclude={"password"}),
            "groups": [g.model_dump() for g in self.config_service.list_groups(project.uuid)],
            "resources": [r.model_dump() for r in self.config_service.list_resources(project.uuid)],
            "state_keys": list(state_db.keys()),
        }

    def _deploy_foundation(self, project: ProjectConfig, cloud: str, region: str):
        state_key = f"foundation:{cloud}:{region}"
        existing = self._get_state(project.uuid, state_key)
        module = _load_cloud_class(cloud, "foundation", "Foundation")
        cm = ConfigurationManager()
        domain = cm.get(f"{cloud}.domain")
        req = FoundationRequest(
            project=project.name,
            project_uuid=project.uuid,
            cloud=cloud,
            region=region,
            domain=domain,
            ssh_key=cm.get("ssh.key"),
            tags=cm.get("tags") or cm.get(f"{cloud}.tags"),
        )
        if existing and (existing.get("vpc_id") or existing.get("network_id") or existing.get("resource_group")):
            logger.info(f"Foundation for {cloud}/{region} already recorded; reconciling")
            result = module.import_resources(req)
        else:
            result = module.create(req)
        self._save_state(project.uuid, state_key, result.model_dump())
        return result

    def _deploy_group_nodes(self, project: ProjectConfig, group: NodeGroupConfig, password: str):
        results = []
        module = _load_cloud_class(group.cloud, "node", "Node")
        for number in range(1, (group.count or 1) + 1):
            state_key = f"node:{group.name}:{number}"
            existing = self._get_state(project.uuid, state_key)
            req = NodeRequest(
                project=project.name,
                project_uuid=project.uuid,
                cloud=group.cloud,
                region=group.region or project.region,
                name=group.name,
                group=group.group,
                number=number,
                build=group.build,
                zone=group.availability_zone,
                os_id=group.os_id,
                os_version=group.os_version,
                os_arch=group.os_arch,
                machine_type=group.machine_type,
                machine_name=group.machine_name,
                services=group.services,
                volume_size=group.volume_size,
                volume_iops=group.volume_iops,
                volume_type=group.volume_type,
                volume_tier=group.volume_tier,
                root_size=group.root_size,
                ports=group.ports,
                tags=group.tags,
                allow=group.allow,
                ssh_key=group.ssh_key,
                ephemeral=group.ephemeral,
                auth_mode=group.auth_mode,
                feature=group.feature,
                finalizer=group.finalizer,
                variables=group.variables,
                profile=group.profile,
            )
            if existing and existing.get("instance_id"):
                logger.info(f"Node {group.name}-{number} already exists; skipping create")
                from couchformation.models.cloud_ops import NodeResult
                result = NodeResult.model_validate({**existing, "project": project.name, "project_uuid": project.uuid, "cloud": group.cloud, "name": group.name, "group": group.group, "number": number})
            else:
                result = module.create(req)
            self._save_state(project.uuid, state_key, result.model_dump())
            results.append(result)
        return results

    def _deploy_resource(self, project: ProjectConfig, resource, password: str):
        state_key = f"resource:{resource.name}"
        existing = self._get_state(project.uuid, state_key)
        module = _load_cloud_class(resource.cloud, "resource", "Resource")
        req = ResourceRequest(
            project=project.name,
            project_uuid=project.uuid,
            cloud=resource.cloud,
            name=resource.name,
            region=resource.region or project.region,
            build=resource.build,
            provider=resource.provider,
            machine_type=resource.machine_type,
            quantity=resource.quantity,
            cidr=resource.cidr,
            allow=resource.allow,
            username=resource.username,
            password=resource.password or password,
            sw_version=resource.sw_version,
            type=resource.type,
            peer_project=resource.peer_project,
            peer_region=resource.peer_region,
            profile=resource.profile,
            account_email=resource.account_email,
            tags=resource.tags,
        )
        if existing and existing.get("resource_id"):
            logger.info(f"Resource {resource.name} already exists; skipping create")
            result = module.import_resources(req)
        else:
            result = module.create(req)
        self._save_state(project.uuid, state_key, result.model_dump())
        return result

    def _run_finalizers(self, project: ProjectConfig, group: NodeGroupConfig, nodes, password: str) -> None:
        from couchformation.finalizers.runner import FinalizerRunner

        FinalizerRunner().run(project=project, group=group, nodes=nodes, password=password)

    def _save_state(self, project_uuid: str, key: str, value: dict) -> None:
        state_db = KeyValueStore(get_project_state_db(project_uuid), "state")
        state_db[key] = json.dumps(value)

    def _get_state(self, project_uuid: str, key: str) -> Optional[dict]:
        state_db = KeyValueStore(get_project_state_db(project_uuid), "state")
        raw = state_db.get(key)
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
