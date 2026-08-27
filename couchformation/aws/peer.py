from __future__ import annotations

import logging

from couchformation.aws.network import AWSNetwork
from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.models.cloud_ops import PeerRequest, PeerResult
from couchformation.resources.config_manager import ConfigurationManager

logger = logging.getLogger("couchformation.aws.peer")
logger.addHandler(logging.NullHandler())


class Peer:
    def create(self, request: PeerRequest) -> PeerResult:
        params = self._prepare(request)
        network = AWSNetwork(params)
        network.peer_vpc()
        return self._result(request, network, accepted=True)

    def destroy(self, request: PeerRequest) -> PeerResult:
        params = self._prepare(request)
        network = AWSNetwork(params)
        network.unpeer_vpc()
        return self._result(request, network, accepted=False)

    def _prepare(self, request: PeerRequest) -> dict:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "aws"
        params.setdefault("name", "foundation")
        cm = ConfigurationManager()
        if not params.get("ssh_key"):
            params["ssh_key"] = cm.get("ssh.key")
        return params

    @staticmethod
    def _result(request: PeerRequest, network: AWSNetwork, accepted: bool) -> PeerResult:
        state = state_to_dict(network.state)
        return PeerResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="aws",
            region=request.region,
            peering_id=state.get("peering_id"),
            peer_cidr=state.get("peer_cidr"),
            peer_hosted_zone=state.get("peer_hosted_zone"),
            accepted=accepted and bool(state.get("peering_id")),
            state=state,
        )
