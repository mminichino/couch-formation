import pytest

from couchformation.azure.auth import Auth
from couchformation.azure.foundation import Foundation
from couchformation.azure.resource import Resource
from couchformation.identity.id import UniqueId
from couchformation.models.cloud_ops import AuthRequest, FoundationRequest, ResourceRequest

pytestmark = [pytest.mark.integration, pytest.mark.cf_azure]


@pytest.fixture
def project_ids():
    uid = UniqueId()
    return uid.uuid, f"cf-int-{uid.min}"


def test_azure_auth_and_foundation(project_ids, cleanup):
    project_uuid, project_name = project_ids
    Auth().configure(AuthRequest(cloud="azure", region="eastus"))
    req = FoundationRequest(project=project_name, project_uuid=project_uuid, cloud="azure", region="eastus")
    foundation = Foundation()
    created = foundation.create(req)
    cleanup(lambda: foundation.destroy(req))
    assert created.resource_group or created.network_name or created.state
    resource = Resource().create(ResourceRequest(project=project_name, project_uuid=project_uuid, cloud="azure", name="noop"))
    assert resource.created is False
