from __future__ import annotations

import logging

from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.gcp.network import GCPNetwork
from couchformation.models.cloud_ops import FoundationRequest, FoundationResult, ZoneResult
from couchformation.resources.config_manager import ConfigurationManager

logger = logging.getLogger("couchformation.gcp.foundation")
logger.addHandler(logging.NullHandler())


class Foundation:
    def create(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = GCPNetwork(params)
        network.create_vpc()
        return self._result(request, network)

    def destroy(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = GCPNetwork(params)
        network.destroy_vpc()
        return self._result(request, network)

    def import_resources(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = GCPNetwork(params)
        network.check_state()
        return self._result(request, network)

    def _prepare(self, request: FoundationRequest) -> dict:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "gcp"
        params.setdefault("name", request.name or "foundation")
        cm = ConfigurationManager()
        if not params.get("domain"):
            params["domain"] = cm.get("gcp.domain")
        return params

    @staticmethod
    def _result(request: FoundationRequest, network: GCPNetwork) -> FoundationResult:
        state = state_to_dict(network.state)
        zones = [
            ZoneResult(zone=z[0] if isinstance(z, (list, tuple)) else z.get("zone"), subnet_name=getattr(network, "subnet_name", None))
            for z in (getattr(network, "zones", None) or [])
        ]
        return FoundationResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="gcp",
            region=request.region,
            network_id=state.get("network"),
            network_name=getattr(network, "vpc_name", None),
            vpc_cidr=state.get("network_cidr"),
            domain=state.get("domain"),
            public_hosted_zone=state.get("public_managed_zone"),
            private_hosted_zone=state.get("private_managed_zone"),
            zones=zones,
            state=state,
        )
