#!/usr/bin/env python3

import time
import warnings
import logging
import base64

import dns.resolver
import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3.util.retry import Retry

from couchformation.models.project import ProjectCreateRequest, ResourceCreateRequest
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService

pytestmark = [
    pytest.mark.capella,
    pytest.mark.cf_capella,
]

warnings.filterwarnings("ignore")

PROJECT = "pytest-capella-v5"


class BasicAuth(AuthBase):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __call__(self, r):
        auth_hash = f"{self.username}:{self.password}"
        auth_encoded = base64.b64encode(auth_hash.encode("ascii"))
        r.headers.update({"Authorization": f"Basic {auth_encoded.decode('ascii')}"})
        return r


@pytest.fixture(autouse=True)
def _cleanup_logging():
    yield
    time.sleep(0.2)
    loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
    for logger in loggers:
        for handler in getattr(logger, "handlers", []):
            logger.removeHandler(handler)


def test_create_capella_resources():
    svc = ProjectConfigService()
    existing = svc.find_by_name(PROJECT)
    if existing:
        try:
            ProjectDeployService().destroy(PROJECT)
        except Exception:
            pass
        svc.delete_project(PROJECT)

    project = svc.create_project(ProjectCreateRequest(name=PROJECT, cloud="capella", region="us-east-1"))
    svc.create_resource(
        project.uuid,
        ResourceCreateRequest(
            name="test-cluster",
            cloud="capella",
            region="us-east-1",
            provider="aws",
            quantity=3,
            machine_type="4x16",
            type="database",
        ),
    )
    resources = svc.list_resources(project.uuid)
    assert any(r.name == "test-cluster" for r in resources)


def test_deploy_capella_resource():
    result = ProjectDeployService().deploy(PROJECT)
    assert "resources" in result


def test_capella_endpoint_available():
    status = ProjectDeployService().status(PROJECT)
    project = ProjectConfigService().resolve(PROJECT)
    password = project.password
    state = None
    from couchformation.services.deploy import ProjectDeployService as PDS
    raw = PDS()._get_state(project.uuid, "resource:test-cluster")
    assert raw
    connect_string = raw.get("endpoint") or raw.get("state", {}).get("connect_string") or raw.get("state", {}).get("srv")
    if not connect_string:
        pytest.skip("No Capella connect string in state")
    username = "Administrator"
    srv_records = dns.resolver.resolve("_couchbases._tcp." + connect_string, "SRV")
    connect_name = str(srv_records[0].target).rstrip(".")
    session = requests.Session()
    retries = Retry(total=10, backoff_factor=0.01, status_forcelist=[500, 501, 503])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    response = requests.get(
        f"https://{connect_name}:18091/pools/default",
        verify=False,
        timeout=15,
        auth=BasicAuth(username, password),
    )
    assert response.status_code == 200


def test_destroy_capella_project():
    ProjectDeployService().destroy(PROJECT)
    ProjectConfigService().delete_project(PROJECT)
