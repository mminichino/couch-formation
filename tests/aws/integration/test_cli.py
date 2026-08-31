#!/usr/bin/env python3

import json
import logging
import time
import warnings
from typing import Optional

import pytest
from typer.testing import CliRunner

from couchformation.cli.cloudmgr import app
from couchformation.config import get_project_state_db
from couchformation.kvdb import KeyValueStore
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService
from couchbase_connect import CouchbaseConfig, open_connection

pytestmark = [
    pytest.mark.integration,
    pytest.mark.cf_aws,
]
warnings.filterwarnings("ignore")

PROJECT = "pytest-aws-v5"
CLOUD = "aws"
REGION = "us-east-2"
COUNT = "3"
MACHINE_TYPE = "8x32"
FINALIZER = "couchbase"


@pytest.fixture(autouse=True)
def _cleanup_logging():
    yield
    time.sleep(0.2)
    loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
    for logger in loggers:
        for handler in getattr(logger, "handlers", []):
            logger.removeHandler(handler)


def _extract_public_ip(deploy_output: str, project_name: str) -> Optional[str]:
    try:
        data = json.loads(deploy_output)
        for node in data.get("nodes", []):
            if node.get("public_ip"):
                return node["public_ip"]
    except Exception:
        pass

    project = ProjectConfigService().find_by_name(project_name)
    if project:
        state_db = KeyValueStore(get_project_state_db(project.uuid), "meta")
        for key in state_db.keys():
            if key.startswith("node:"):
                node_data = state_db.get(key)
                if isinstance(node_data, dict) and node_data.get("public_ip"):
                    return node_data["public_ip"]
    return None


def _verify_couchbase_connection(public_ip: str, password: str) -> None:
    connected = False
    last_error = None
    for ssl_mode in [False, True]:
        try:
            config = (
                CouchbaseConfig()
                .connect(public_ip, "Administrator", password)
                .with_connect_timeout(30)
                .with_kv_timeout(10)
                .with_query_timeout(10)
                .ssl(ssl_mode)
            )
            with open_connection(config) as db:
                db.cluster_wait()
                connected = True
                break
        except Exception as exc:
            last_error = exc

    assert connected, f"Failed to connect to Couchbase at {public_ip}: {last_error or 'Unknown error'}"


def test_cli_couchbase_lifecycle():
    runner = CliRunner()
    svc = ProjectConfigService()

    if svc.find_by_name(PROJECT):
        try:
            ProjectDeployService().destroy(PROJECT)
        except Exception:
            pass
        svc.delete_project(PROJECT)

    create_proj_res = runner.invoke(app, ["create", "project", PROJECT])
    assert create_proj_res.exit_code == 0, f"create project failed: {create_proj_res.output}"

    try:
        create_group_res = runner.invoke(
            app,
            [
                "project",
                PROJECT,
                "create",
                "group",
                "--name",
                "cluster",
                "--cloud",
                CLOUD,
                "--region",
                REGION,
                "--count",
                COUNT,
                "--machine-type",
                MACHINE_TYPE,
                "--finalizer",
                FINALIZER,
            ],
        )
        assert create_group_res.exit_code == 0, f"create group failed: {create_group_res.output}"

        deploy_res = runner.invoke(app, ["project", PROJECT, "deploy"])
        assert deploy_res.exit_code == 0, f"deploy failed: {deploy_res.output}"

        public_ip = _extract_public_ip(deploy_res.stdout, PROJECT)
        assert public_ip, f"No public IP found for project {PROJECT}"

        project = svc.resolve(PROJECT)
        assert project.password, f"No password found for project {PROJECT}"

        _verify_couchbase_connection(public_ip, project.password)
    finally:
        destroy_res = runner.invoke(app, ["project", PROJECT, "destroy"])
        delete_res = runner.invoke(app, ["delete", "project", PROJECT])

        assert destroy_res.exit_code == 0, f"destroy failed: {destroy_res.output}"
        assert delete_res.exit_code == 0, f"delete project failed: {delete_res.output}"
