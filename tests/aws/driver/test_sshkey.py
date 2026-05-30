from __future__ import annotations

import pytest

from couchformation.aws.driver.sshkey import SSHKey
from couchformation.ssh import SSHUtil
from tests.aws.driver.conftest import unique_name

pytestmark = pytest.mark.cf_aws


def test_ssh_key_create_details_delete(aws_parameters, cleanup):
    ssh = SSHKey(aws_parameters)
    key_name = unique_name(f"{aws_parameters['project']}-key")
    ssh_pub_key = SSHUtil().get_ssh_public_key(aws_parameters.get("ssh_key"))

    created_name = ssh.create(key_name, ssh_pub_key, tags={"Environment": "pytest"})
    cleanup(lambda: ssh.delete(created_name))
    assert created_name == key_name

    details = ssh.details(key_name)
    assert details is not None
    assert details["name"] == key_name
    assert details["fingerprint"]

    listed = ssh.list()
    assert any(item["name"] == key_name for item in listed)

    ssh.delete(key_name)
    assert ssh.details(key_name) is None
