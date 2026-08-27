from __future__ import annotations

import logging

from couchformation.azure.network import AzureNetwork
from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.models.cloud_ops import PeerRequest, PeerResult

logger = logging.getLogger("couchformation.azure.peer")
logger.addHandler(logging.NullHandler())


class Peer:
    def create(self, request: PeerRequest) -> PeerResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "azure"
        params.setdefault("name", "foundation")
        network = AzureNetwork(params)
        if hasattr(network, "peer_vpc"):
            network.peer_vpc()
        state = state_to_dict(network.state)
        return PeerResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="azure",
            region=request.region,
            peering_id=state.get("peering_id"),
            accepted=bool(state.get("peering_id")),
            state=state,
        )

    def destroy(self, request: PeerRequest) -> PeerResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "azure"
        params.setdefault("name", "foundation")
        network = AzureNetwork(params)
        if hasattr(network, "unpeer_vpc"):
            network.unpeer_vpc()
        return PeerResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="azure",
            region=request.region,
            accepted=False,
            state=state_to_dict(network.state),
        )
