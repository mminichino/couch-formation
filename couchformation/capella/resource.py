from __future__ import annotations

import logging

from couchformation.capella.node import CapellaDeployment
from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.models.cloud_ops import ResourceRequest, ResourceResult

logger = logging.getLogger("couchformation.capella.resource")
logger.addHandler(logging.NullHandler())


class Resource:
    def create(self, request: ResourceRequest) -> ResourceResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "capella"
        deployment = CapellaDeployment(params)
        state = deployment.deploy() if hasattr(deployment, "deploy") else {}
        if state is None:
            state = state_to_dict(deployment.state)
        return ResourceResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="capella",
            name=request.name,
            resource_id=state.get("instance_id") or state.get("cluster_id"),
            resource_name=state.get("instance_name") or request.name,
            endpoint=state.get("endpoint") or state.get("srv"),
            created=True,
            state=state if isinstance(state, dict) else state_to_dict(state),
        )

    def destroy(self, request: ResourceRequest) -> ResourceResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "capella"
        deployment = CapellaDeployment(params)
        if hasattr(deployment, "destroy"):
            deployment.destroy()
        return ResourceResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="capella",
            name=request.name,
            created=False,
            state=state_to_dict(deployment.state),
        )

    def import_resources(self, request: ResourceRequest) -> ResourceResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "capella"
        deployment = CapellaDeployment(params)
        state = deployment.info() if hasattr(deployment, "info") else state_to_dict(deployment.state)
        return ResourceResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="capella",
            name=request.name,
            resource_id=(state or {}).get("instance_id"),
            resource_name=(state or {}).get("instance_name"),
            created=bool((state or {}).get("instance_id")),
            state=state or {},
        )
