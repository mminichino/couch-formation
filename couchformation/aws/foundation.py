from __future__ import annotations

import logging

from couchformation.aws.network import AWSNetwork
from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.models.cloud_ops import (
    FoundationRequest,
    FoundationResult,
    ZoneResult,
)
from couchformation.resources.config_manager import ConfigurationManager

logger = logging.getLogger("couchformation.aws.foundation")
logger.addHandler(logging.NullHandler())


class Foundation:
    def create(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = AWSNetwork(params)
        network.create_vpc()
        return self._result_from_network(request, network)

    def destroy(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = AWSNetwork(params)
        network.destroy_vpc()
        return self._result_from_network(request, network)

    def import_resources(self, request: FoundationRequest) -> FoundationResult:
        params = self._prepare(request)
        network = AWSNetwork(params)
        network.check_state()
        return self._result_from_network(request, network)

    def _prepare(self, request: FoundationRequest) -> dict:
        params = request.to_parameters()
        project_uuid = resolve_project_uuid(params)
        params["project_uuid"] = project_uuid
        params["cloud"] = "aws"
        params.setdefault("name", request.name or "foundation")
        cm = ConfigurationManager()
        if not params.get("domain"):
            params["domain"] = cm.get("aws.domain")
        if not params.get("ssh_key"):
            params["ssh_key"] = cm.get("ssh.key")
        return params

    @staticmethod
    def _result_from_network(request: FoundationRequest, network: AWSNetwork) -> FoundationResult:
        zones = []
        for zone_state in network.zones or []:
            zones.append(
                ZoneResult(
                    zone=zone_state[0],
                    cidr=zone_state[1] if len(zone_state) > 1 else None,
                    subnet_id=zone_state[2] if len(zone_state) > 2 else None,
                )
            )
        state = state_to_dict(network.state)
        return FoundationResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="aws",
            region=request.region,
            vpc_id=network.vpc_id,
            vpc_name=getattr(network, "vpc_name", None),
            vpc_cidr=state.get("vpc_cidr"),
            security_group_id=network.security_group_id,
            ssh_key=network.ssh_key_id,
            internet_gateway_id=state.get("internet_gateway_id"),
            route_table_id=state.get("route_table_id"),
            domain=network.domain_name,
            public_hosted_zone=network.public_zone,
            private_hosted_zone=network.private_zone,
            zones=zones,
            state=state,
        )
