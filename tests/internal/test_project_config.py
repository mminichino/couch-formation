import pytest

from couchformation.models.project import GroupCreateRequest, ProjectCreateRequest
from couchformation.services.config import ProjectConfigService
from couchformation.util import PasswordUtility

pytestmark = [pytest.mark.cf_posix]


def test_password_rules():
    for _ in range(20):
        password = PasswordUtility().generate(16)
        assert len(password) == 16
        assert password[0].isalnum()
        assert PasswordUtility.valid_password(password, 16, 16)
        assert sum(1 for c in password if c in "#-_") == 1


def test_project_config_and_finalizer_groups(tmp_path, monkeypatch):
    monkeypatch.setenv("COUCH_FORMATION_ROOT_DIR", str(tmp_path))
    svc = ProjectConfigService()
    project = svc.create_project(ProjectCreateRequest(name="unitproj", cloud="aws", region="us-east-2"))
    assert project.uuid
    assert len(project.password) == 16

    g0 = svc.create_group(project.uuid, GroupCreateRequest(name="a", cloud="aws", finalizer="couchbase"))
    g1 = svc.create_group(project.uuid, GroupCreateRequest(name="b", cloud="aws"))
    g2 = svc.create_group(project.uuid, GroupCreateRequest(name="c", cloud="aws", finalizer="couchbase"))
    assert g0.group == 0
    assert g0.finalizer_group == 0
    assert g1.finalizer_group is None
    assert g2.finalizer_group == 1

    projects = svc.list_projects()
    assert any(p.name == "unitproj" for p in projects)
    svc.delete_project(project.uuid)
    assert svc.find_by_name("unitproj") is None


def test_cli_config_get_all(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from couchformation.cli.cloudmgr import app
    from couchformation.resources.config_manager import ConfigurationManager

    monkeypatch.setenv("COUCH_FORMATION_ROOT_DIR", str(tmp_path))
    cm = ConfigurationManager()
    cm.set("aws.domain", "example.com")
    cm.set("gcp.domain", "gcp.example.com")

    runner = CliRunner()
    result = runner.invoke(app, ["config", "get", "--all"])
    assert result.exit_code == 0
    assert "aws.domain = example.com" in result.stdout
    assert "gcp.domain = gcp.example.com" in result.stdout

    result_short = runner.invoke(app, ["config", "get", "-a"])
    assert result_short.exit_code == 0
    assert "aws.domain = example.com" in result_short.stdout

    result_single = runner.invoke(app, ["config", "get", "aws.domain"])
    assert result_single.exit_code == 0
    assert result_single.stdout.strip() == "aws.domain = example.com"


def test_asset_names_aws_security_group_prefix():
    import uuid
    from couchformation.cloud_common import asset_names

    names = asset_names(str(uuid.uuid4()))
    assert not names["sg_name"].startswith("sg-"), "AWS GroupName must not start with sg-"
    assert names["sg_name"].startswith("secgrp-")


def test_aws_dns_region_attribute(monkeypatch):
    from unittest.mock import MagicMock
    from couchformation.aws.driver.dns import DNS

    dns = DNS()
    dns.session = MagicMock()
    dns.session.region_name = "us-east-2"
    assert dns.region == "us-east-2"
    dns.dns_client = MagicMock()
    dns.dns_client.create_hosted_zone.return_value = {"HostedZone": {"Id": "/hostedzone/Z12345"}}

    # Verify create() calls without error when region is None (falls back to self.region)
    zone_id = dns.create("test.example.com", vpc_id="vpc-123")
    assert zone_id == "Z12345"
    dns.dns_client.create_hosted_zone.assert_called_once()
    call_kwargs = dns.dns_client.create_hosted_zone.call_args[1]
    assert call_kwargs["VPC"]["VPCRegion"] == "us-east-2"


def test_aws_image_list_standard_ubuntu_24_04():
    from unittest.mock import MagicMock
    from couchformation.aws.driver.image import Image

    image = Image()
    image.list = MagicMock(return_value=[
        {
            "id": "ami-ubuntu2404",
            "name": "ami-ubuntu2404",
            "description": "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20240423",
            "arch": "x86_64",
            "date": "2024-04-23T00:00:00.000Z",
            "state": "available",
        }
    ])

    res = image.list_standard(os_id="ubuntu", os_version="24.04")
    assert res is not None
    assert res["name"] == "ami-ubuntu2404"
    assert res["os_id"] == "ubuntu"
    assert res["os_version"] == "24.04"

    # Also test when no images match
    image.list = MagicMock(return_value=[])
    res_none = image.list_standard(os_id="ubuntu", os_version="99.99")
    assert res_none is None


def test_gcp_image_list_standard_ubuntu_24_04():
    from unittest.mock import MagicMock
    from couchformation.gcp.driver.image import Image

    image = Image()
    image.list = MagicMock(return_value=[
        {
            "name": "ubuntu-2404-noble-amd64-v20240423",
            "selfLink": "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20240423",
            "date": "2024-04-23T00:00:00.000-07:00",
        }
    ])

    res = image.list_standard(os_id="ubuntu", os_version="24.04")
    assert res is not None
    assert res["os_id"] == "ubuntu"
    assert res["os_version"] == "24.04"
    assert res["image_project"] == "ubuntu-os-cloud"


def test_azure_image_list_standard_ubuntu_24_04():
    from unittest.mock import MagicMock
    from couchformation.azure.driver.image import Image

    image = Image()
    image.public = MagicMock(return_value=[
        {
            "publisher": "Canonical",
            "offer": "0001-com-ubuntu-server-noble",
            "sku": "24_04-lts-gen2",
            "version": "24.04.202404230",
        }
    ])

    res = image.list_standard(os_id="ubuntu", os_version="24.04")
    assert res is not None
    assert res["os_id"] == "ubuntu"
    assert res["os_version"] == "24.04"


def test_finalizer_runner_and_couchbase_rebalance(monkeypatch):
    import io
    from couchformation.finalizers.runner import FinalizerRunner
    from couchformation.models.cloud_ops import NodeResult
    from couchformation.models.project import NodeGroupConfig, ProjectConfig

    executed_commands = []

    def mock_run_ssh_command(ssh_key, username, host, command, working_dir):
        class MockSSH:
            def exec(self):
                executed_commands.append((host, command))
                return 0, io.StringIO("ok"), io.StringIO("")
        return MockSSH()

    monkeypatch.setattr("couchformation.finalizers.base.RunSSHCommand", mock_run_ssh_command)
    monkeypatch.setattr("couchformation.resources.config_manager.ConfigurationManager.get", lambda self, k: "/fake/key")

    project = ProjectConfig(name="testproj", uuid="12345678-1234-5678-1234-567812345678", cloud="aws")
    group0 = NodeGroupConfig(name="g0", group=0, count=2, cloud="aws", finalizer="couchbase", finalizer_group=0)
    group1 = NodeGroupConfig(name="g1", group=1, count=1, cloud="aws", finalizer="couchbase", finalizer_group=1)

    node0_1 = NodeResult(project="testproj", project_uuid=project.uuid, cloud="aws", name="g0", group=0, number=1, node_name="g0-node-01", username="ubuntu", private_ip="10.0.0.1", public_ip="1.1.1.1", zone="us-east-2a")
    node0_2 = NodeResult(project="testproj", project_uuid=project.uuid, cloud="aws", name="g0", group=0, number=2, node_name="g0-node-02", username="ubuntu", private_ip="10.0.0.2", public_ip="1.1.1.2", zone="us-east-2b")
    node1_1 = NodeResult(project="testproj", project_uuid=project.uuid, cloud="aws", name="g1", group=1, number=1, node_name="g1-node-01", username="ubuntu", private_ip="10.0.0.3", public_ip="1.1.1.3", zone="us-east-2c")

    runner = FinalizerRunner()
    runner.run(
        project=project,
        group_or_groups=[(group0, [node0_1, node0_2]), (group1, [node1_1])],
        password="TestPassword123#",
    )

    # Verify primary node ran create
    assert any("swmgr cluster --name testproj" in cmd and "create" in cmd and host == "1.1.1.1" for host, cmd in executed_commands)
    # Verify non-primary nodes ran add with rally-ip
    assert any("swmgr cluster --password TestPassword123# --rally-ip-address 10.0.0.1" in cmd and "add" in cmd and host == "1.1.1.2" for host, cmd in executed_commands)
    assert any("swmgr cluster --password TestPassword123# --rally-ip-address 10.0.0.1" in cmd and "add" in cmd and host == "1.1.1.3" for host, cmd in executed_commands)
    # Verify final rebalance command was executed on primary node
    assert any("swmgr cluster --password TestPassword123# --rally-ip-address 10.0.0.1 rebalance" in cmd and host == "1.1.1.1" for host, cmd in executed_commands)
    # Verify commands used sudo
    assert any("sudo bundlemgr -b CBS" in cmd for _, cmd in executed_commands)
    assert any("sudo swmgr" in cmd for _, cmd in executed_commands)
    # Verify asdf and python 3.12.13 install commands
    assert any("asdf install python 3.12.13" in cmd for _, cmd in executed_commands)


def test_execute_node_command_checks_return_status(monkeypatch):
    import io
    import pytest
    from couchformation.finalizers.base import execute_node_command
    from couchformation.models.cloud_ops import NodeResult
    from couchformation.models.project import NodeGroupConfig

    def mock_run_ssh_fail(ssh_key, username, host, command, working_dir):
        class MockSSH:
            def exec(self):
                return 1, io.StringIO(""), io.StringIO("Fatal error during execution")
        return MockSSH()

    monkeypatch.setattr("couchformation.finalizers.base.RunSSHCommand", mock_run_ssh_fail)
    monkeypatch.setattr("couchformation.resources.config_manager.ConfigurationManager.get", lambda self, k: "/fake/key")

    node = NodeResult(project="testproj", project_uuid="123", cloud="aws", name="g0", group=0, number=1, username="ubuntu", private_ip="10.0.0.1", public_ip="1.1.1.1")
    group = NodeGroupConfig(name="g0", group=0, cloud="aws")

    with pytest.raises(RuntimeError, match="failed on 1.1.1.1 with exit code 1"):
        execute_node_command(node, group, "some_failing_command", check=True)


def test_deploy_destroy_clears_state(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from couchformation.services.config import ProjectConfigService
    from couchformation.services.deploy import ProjectDeployService
    from couchformation.models.project import ProjectCreateRequest, GroupCreateRequest
    from couchformation.models.cloud_ops import FoundationResult, NodeResult

    monkeypatch.setenv("COUCH_FORMATION_ROOT_DIR", str(tmp_path))

    cfg_svc = ProjectConfigService()
    deploy_svc = ProjectDeployService()

    project = cfg_svc.create_project(ProjectCreateRequest(name="testdest", cloud="aws", region="us-east-2"))
    group = cfg_svc.create_group(project.uuid, GroupCreateRequest(name="cluster", count=2, cloud="aws", region="us-east-2"))

    mock_foundation = MagicMock()
    mock_foundation.create.return_value = FoundationResult(
        project=project.name, project_uuid=project.uuid, cloud="aws", region="us-east-2", vpc_id="vpc-111"
    )
    mock_foundation.destroy.return_value = FoundationResult(
        project=project.name, project_uuid=project.uuid, cloud="aws", region="us-east-2"
    )

    mock_node = MagicMock()
    mock_node.create.side_effect = [
        NodeResult(project=project.name, project_uuid=project.uuid, cloud="aws", name="cluster", group=0, number=1, instance_id="i-1", public_ip="1.1.1.1", private_ip="10.0.0.1"),
        NodeResult(project=project.name, project_uuid=project.uuid, cloud="aws", name="cluster", group=0, number=2, instance_id="i-2", public_ip="1.1.1.2", private_ip="10.0.0.2"),
    ]
    mock_node.destroy.return_value = NodeResult(project=project.name, project_uuid=project.uuid, cloud="aws", name="cluster", group=0, number=1)

    monkeypatch.setattr("couchformation.services.deploy._load_cloud_class", lambda cloud, mod, cls: mock_foundation if mod == "foundation" else mock_node)
    monkeypatch.setattr("couchformation.services.deploy.ProjectDeployService._run_finalizers", lambda self, p, g, pwd: None)

    # 1. Deploy
    deploy_svc.deploy(project.uuid)
    assert deploy_svc._get_state(project.uuid, "foundation:aws:us-east-2") is not None
    assert deploy_svc._get_state(project.uuid, "node:cluster:1") is not None
    assert deploy_svc._get_state(project.uuid, "node:cluster:2") is not None

    # 2. Destroy
    deploy_svc.destroy(project.uuid)
    assert deploy_svc._get_state(project.uuid, "foundation:aws:us-east-2") is None
    assert deploy_svc._get_state(project.uuid, "node:cluster:1") is None
    assert deploy_svc._get_state(project.uuid, "node:cluster:2") is None


def test_default_services_couchbase_finalizer():
    from couchformation.finalizers.couchbase import CouchbaseFinalizer
    from couchformation.models.cloud_ops import NodeResult
    from couchformation.models.project import NodeGroupConfig, ProjectConfig

    executed = []
    def mock_exec(node, group, cmd, password=None, check=True):
        executed.append(cmd)

    import couchformation.finalizers.couchbase as cb_mod
    orig_exec = cb_mod.execute_node_command
    cb_mod.execute_node_command = mock_exec
    try:
        project = ProjectConfig(name="testcb", uuid="12345", cloud="aws")
        group = NodeGroupConfig(name="g0", group=0, cloud="aws", services="default")
        node = NodeResult(project="testcb", project_uuid="12345", cloud="aws", name="g0", group=0, number=1, private_ip="10.0.0.1", public_ip="1.1.1.1")
        CouchbaseFinalizer().run(project, group, node, "password", {})
        assert any("--services data,index,query,fts" in cmd for cmd in executed)
    finally:
        cb_mod.execute_node_command = orig_exec








