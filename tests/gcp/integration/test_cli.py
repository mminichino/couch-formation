#!/usr/bin/env python3

import time
import warnings
import logging

import pytest

from couchformation.models.project import GroupCreateRequest, ProjectCreateRequest
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService
from couchformation.services.importer import ProjectImportService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.cf_gcp,
]
warnings.filterwarnings("ignore")

PROJECT = "pytest-gcp-v5"


@pytest.fixture(autouse=True)
def _cleanup_logging():
    yield
    time.sleep(0.2)
    loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
    for logger in loggers:
        for handler in getattr(logger, "handlers", []):
            logger.removeHandler(handler)


def test_create_project_and_group():
    svc = ProjectConfigService()
    existing = svc.find_by_name(PROJECT)
    if existing:
        try:
            ProjectDeployService().destroy(PROJECT)
        except Exception:
            pass
        svc.delete_project(PROJECT)
    project = svc.create_project(ProjectCreateRequest(name=PROJECT, cloud="gcp", region="us-central1"))
    group = svc.create_group(
        project.uuid,
        GroupCreateRequest(
            name="test-cluster",
            cloud="gcp",
            region="us-central1",
            count=1,
            os_id="ubuntu",
            os_version="24.04",
            machine_type="4x16",
            build="cbs",
        ),
    )
    assert group.group == 0


def test_deploy_import_destroy():
    deploy = ProjectDeployService()
    deploy.deploy(PROJECT)
    ProjectImportService().import_project(PROJECT)
    deploy.destroy(PROJECT)
    ProjectConfigService().delete_project(PROJECT)
