from __future__ import annotations

import logging

from couchformation.models.cloud_ops import FoundationRequest, FoundationResult

logger = logging.getLogger("couchformation.capella.foundation")
logger.addHandler(logging.NullHandler())


class Foundation:
    def create(self, request: FoundationRequest) -> FoundationResult:
        logger.debug("Capella foundation create is a no-op")
        return FoundationResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="capella",
            region=request.region,
        )

    def destroy(self, request: FoundationRequest) -> FoundationResult:
        return self.create(request)

    def import_resources(self, request: FoundationRequest) -> FoundationResult:
        return self.create(request)
