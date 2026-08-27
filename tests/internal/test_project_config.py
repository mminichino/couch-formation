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
