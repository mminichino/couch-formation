from __future__ import annotations

import importlib
import logging
from typing import Any

from couchformation.exception import FatalError
from couchformation.models.cloud_ops import FoundationRequest, NodeRequest, ResourceRequest
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService, _load_cloud_class

logger = logging.getLogger("couchformation.services.importer")
logger.addHandler(logging.NullHandler())


class ProjectImportError(FatalError):
    pass


class ProjectImportService:
    def __init__(self):
        self.config_service = ProjectConfigService()
        self.deploy_service = ProjectDeployService()

    def import_project(self, name_or_uuid: str) -> dict[str, Any]:
        project = self.config_service.resolve(name_or_uuid)
        imported: dict[str, Any] = {"project": project.model_dump(exclude={"password"}), "foundations": [], "nodes": [], "resources": []}

        groups = self.config_service.list_groups(project.uuid)
        clouds_regions = {(g.cloud, g.region or project.region) for g in groups if g.cloud != "capella"}
        for cloud, region in clouds_regions:
            if not region:
                continue
            module = _load_cloud_class(cloud, "foundation", "Foundation")
            req = FoundationRequest(
                project=project.name,
                project_uuid=project.uuid,
                cloud=cloud,
                region=region,
            )
            result = module.import_resources(req)
            self.deploy_service._save_state(project.uuid, f"foundation:{cloud}:{region}", result.model_dump())
            imported["foundations"].append(result.model_dump())

        for group in groups:
            if group.cloud == "capella":
                continue
            module = _load_cloud_class(group.cloud, "node", "Node")
            for number in range(1, (group.count or 1) + 1):
                req = NodeRequest(
                    project=project.name,
                    project_uuid=project.uuid,
                    cloud=group.cloud,
                    region=group.region or project.region,
                    name=group.name,
                    group=group.group,
                    number=number,
                )
                result = module.info(req)
                self.deploy_service._save_state(project.uuid, f"node:{group.name}:{number}", result.model_dump())
                imported["nodes"].append(result.model_dump())

        for resource in self.config_service.list_resources(project.uuid):
            module = _load_cloud_class(resource.cloud, "resource", "Resource")
            req = ResourceRequest(
                project=project.name,
                project_uuid=project.uuid,
                cloud=resource.cloud,
                name=resource.name,
                region=resource.region or project.region,
            )
            result = module.import_resources(req)
            self.deploy_service._save_state(project.uuid, f"resource:{resource.name}", result.model_dump())
            imported["resources"].append(result.model_dump())

        logger.info(f"Imported cloud state for project {project.name}")
        return imported
