#!/usr/bin/env python3

import time
import warnings
import logging

import pytest

from couchformation.models.project import ProjectCreateRequest, ResourceCreateRequest
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService

pytestmark = [
    pytest.mark.capella,
    pytest.mark.cf_capella,
]

warnings.filterwarnings("ignore")

PROJECT = "pytest-capella-col-v5"


@pytest.fixture(autouse=True)
def _cleanup_logging():
    yield
    time.sleep(0.2)
    loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
    for logger in loggers:
        for handler in getattr(logger, "handlers", []):
            logger.removeHandler(handler)


def test_create_columnar_resource():
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
            name="test-columnar",
            cloud="capella",
            region="us-east-1",
            provider="aws",
            quantity=1,
            type="columnar",
        ),
    )


def test_deploy_and_destroy_columnar():
    ProjectDeployService().deploy(PROJECT)
    ProjectDeployService().destroy(PROJECT)
    ProjectConfigService().delete_project(PROJECT)
