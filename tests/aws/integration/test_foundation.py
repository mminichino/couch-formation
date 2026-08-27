import pytest

from couchformation.aws.auth import Auth
from couchformation.aws.foundation import Foundation
from couchformation.aws.peer import Peer
from couchformation.aws.resource import Resource
from couchformation.identity.id import UniqueId
from couchformation.models.cloud_ops import AuthRequest, FoundationRequest, PeerRequest, ResourceRequest

pytestmark = [pytest.mark.integration, pytest.mark.cf_aws]


@pytest.fixture
def project_ids():
    uid = UniqueId()
    return uid.uuid, f"cf-int-{uid.min}"


def test_aws_auth_and_foundation(project_ids, cleanup):
    project_uuid, project_name = project_ids
    Auth().configure(AuthRequest(cloud="aws", region="us-east-2"))
    req = FoundationRequest(
        project=project_name,
        project_uuid=project_uuid,
        cloud="aws",
        region="us-east-2",
    )
    foundation = Foundation()
    created = foundation.create(req)
    cleanup(lambda: foundation.destroy(req))
    assert created.vpc_id
    imported = foundation.import_resources(req)
    assert imported.vpc_id == created.vpc_id
    peer = Peer().create(PeerRequest(project=project_name, project_uuid=project_uuid, cloud="aws", region="us-east-2"))
    assert peer.cloud == "aws"
    resource = Resource().create(ResourceRequest(project=project_name, project_uuid=project_uuid, cloud="aws", name="noop"))
    assert resource.created is False
