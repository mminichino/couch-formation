import pytest

from couchformation.gcp.auth import Auth
from couchformation.gcp.foundation import Foundation
from couchformation.gcp.resource import Resource
from couchformation.identity.id import UniqueId
from couchformation.models.cloud_ops import AuthRequest, FoundationRequest, ResourceRequest

pytestmark = [pytest.mark.integration, pytest.mark.cf_gcp]


@pytest.fixture
def project_ids():
    uid = UniqueId()
    return uid.uuid, f"cf-int-{uid.min}"


def test_gcp_auth_and_foundation(project_ids, cleanup):
    project_uuid, project_name = project_ids
    Auth().configure(AuthRequest(cloud="gcp", region="us-central1"))
    req = FoundationRequest(project=project_name, project_uuid=project_uuid, cloud="gcp", region="us-central1")
    foundation = Foundation()
    created = foundation.create(req)
    cleanup(lambda: foundation.destroy(req))
    assert created.network_name or created.state
    resource = Resource().create(ResourceRequest(project=project_name, project_uuid=project_uuid, cloud="gcp", name="noop"))
    assert resource.created is False
