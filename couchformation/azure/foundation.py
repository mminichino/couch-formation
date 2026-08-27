from __future__ import annotations

import logging

from couchformation.azure.network import AzureNetwork
from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.models.cloud_ops import FoundationRequest, FoundationResult, ZoneResult
from couchformation.resources.config_manager import ConfigurationManager

logger = logging.getLogger("couchformation.azure.foundation")
logger.addHandler(logging.NullHandler())


class Foundation:
    def create(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = AzureNetwork(params)
        network.create_vpc()
        return self._result(request, network)

    def destroy(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = AzureNetwork(params)
        network.destroy_vpc()
        return self._result(request, network)

    def import_resources(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = AzureNetwork(params)
        network.check_state()
        return self._result(request, network)

    def _prepare(self, request: FoundationRequest) -> dict:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "azure"
        params.setdefault("name", request.name or "foundation")
        cm = ConfigurationManager()
        if not params.get("domain"):
            params["domain"] = cm.get("azure.domain")
        return params

    @staticmethod
    def _result(request: FoundationRequest, network: AzureNetwork) -> FoundationResult:
        state = state_to_dict(network.state)
        return FoundationResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="azure",
            region=request.region,
            resource_group=state.get("resource_group") or getattr(network, "rg_name", None),
            network_id=state.get("network_id"),
            network_name=state.get("network") or getattr(network, "vpc_name", None),
            vpc_cidr=state.get("network_cidr"),
            security_group_id=state.get("network_security_group_id"),
            domain=state.get("domain"),
            public_hosted_zone=state.get("public_zone"),
            private_hosted_zone=state.get("private_zone"),
            zones=[ZoneResult(zone=request.region, subnet_id=state.get("subnet_id"), subnet_name=state.get("subnet"))],
            state=state,
        )
