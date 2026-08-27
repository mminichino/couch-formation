from __future__ import annotations

import logging

from couchformation.models.cloud_ops import PeerRequest, PeerResult

logger = logging.getLogger("couchformation.capella.peer")
logger.addHandler(logging.NullHandler())


class Peer:
    def create(self, request: PeerRequest) -> PeerResult:
        logger.debug("Capella peer create is a no-op at foundation layer")
        return PeerResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="capella",
            region=request.region,
            accepted=False,
        )

    def destroy(self, request: PeerRequest) -> PeerResult:
        return self.create(request)
