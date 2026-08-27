#!/usr/bin/env python3

import os
import time
import warnings
import logging

import pytest

from couchformation.models.project import GroupCreateRequest, ProjectCreateRequest
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.cf_aws,
]
warnings.filterwarnings("ignore")

PROJECT = "pytest-aws-v5"


@pytest.fixture(scope="module")
def project_name(tmp_path_factory, monkeypatch_module=None):
    return PROJECT


@pytest.fixture(autouse=True)
def _cleanup_logging():
    yield
    time.sleep(0.2)
    loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
    for logger in loggers:
        for handler in getattr(logger, "handlers", []):
            logger.removeHandler(handler)


def test_create_project_and_groups():
    svc = ProjectConfigService()
    existing = svc.find_by_name(PROJECT)
    if existing:
        svc.delete_project(PROJECT)
    project = svc.create_project(ProjectCreateRequest(name=PROJECT, cloud="aws", region="us-east-2"))
    assert project.uuid
    g0 = svc.create_group(
        project.uuid,
        GroupCreateRequest(
            name="test-cluster",
            cloud="aws",
            region="us-east-2",
            count=3,
            os_id="ubuntu",
            os_version="24.04",
            machine_type="4x16",
            build="cbs",
            finalizer="couchbase",
            variables={"version": "latest"},
        ),
    )
    g1 = svc.create_group(
        project.uuid,
        GroupCreateRequest(
            name="analytics",
            cloud="aws",
            region="us-east-2",
            count=2,
            os_id="ubuntu",
            os_version="24.04",
            machine_type="4x16",
            services="analytics",
            build="cbs",
            finalizer="couchbase",
        ),
    )
    assert g0.group == 0
    assert g1.group == 1
    assert g0.finalizer_group == 0
    assert g1.finalizer_group == 1


def test_deploy_and_status():
    deploy = ProjectDeployService()
    status = deploy.status(PROJECT)
    assert status["project"]["name"] == PROJECT
    result = deploy.deploy(PROJECT)
    assert "foundations" in result
    assert "nodes" in result


def test_import_and_destroy():
    from couchformation.services.importer import ProjectImportService

    imported = ProjectImportService().import_project(PROJECT)
    assert imported["project"]["name"] == PROJECT
    destroyed = ProjectDeployService().destroy(PROJECT)
    assert "destroyed" in destroyed
    ProjectConfigService().delete_project(PROJECT)
