from __future__ import annotations

import logging

from couchformation.cloud_common import resolve_project_uuid, state_to_dict
from couchformation.gcp.network import GCPNetwork
from couchformation.models.cloud_ops import PeerRequest, PeerResult

logger = logging.getLogger("couchformation.gcp.peer")
logger.addHandler(logging.NullHandler())


class Peer:
    def create(self, request: PeerRequest) -> PeerResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "gcp"
        params.setdefault("name", "foundation")
        if request.peer_project:
            params["peer_gcp_project"] = request.peer_project
        network = GCPNetwork(params)
        if hasattr(network, "peer_vpc"):
            network.peer_vpc()
        state = state_to_dict(network.state)
        return PeerResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="gcp",
            region=request.region,
            peering_id=state.get("peering_id") or state.get("peer_name"),
            accepted=True,
            state=state,
        )

    def destroy(self, request: PeerRequest) -> PeerResult:
        params = request.to_parameters()
        params["project_uuid"] = resolve_project_uuid(params)
        params["cloud"] = "gcp"
        params.setdefault("name", "foundation")
        network = GCPNetwork(params)
        if hasattr(network, "unpeer_vpc"):
            network.unpeer_vpc()
        return PeerResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="gcp",
            region=request.region,
            accepted=False,
            state=state_to_dict(network.state),
        )
