from __future__ import annotations

import pytest

from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.image import Image
from couchformation.aws.driver.instance import Instance
from couchformation.aws.driver.network import Network, Subnet
from couchformation.aws.driver.nsg import SecurityGroup
from couchformation.aws.driver.route import RouteTable
from couchformation.aws.driver.sshkey import SSHKey
from couchformation.ssh import SSHUtil
from couchformation.util import parameter_to_dict
from tests.aws.driver.conftest import unique_name

pytestmark = pytest.mark.cf_aws


def test_instance_run_terminate(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    subnet_drv = Subnet(aws_parameters)
    gateway = InternetGateway(aws_parameters)
    route = RouteTable(aws_parameters)
    sg = SecurityGroup(aws_parameters)
    ssh = SSHKey(aws_parameters)
    instance = Instance(aws_parameters)

    vpc_name = unique_name(f"{aws_parameters['project']}-vpc")
    ig_name = unique_name(f"{aws_parameters['project']}-igw")
    rt_name = unique_name(f"{aws_parameters['project']}-rt")
    sg_name = unique_name(f"{aws_parameters['project']}-sg")
    key_name = unique_name(f"{aws_parameters['project']}-key")
    subnet_name = unique_name(f"{aws_parameters['project']}-subnet")
    node_name = unique_name(f"{aws_parameters['project']}-node")

    vpc_cidr = cidr_util.get_next_network()
    subnet_cidr = next(cidr_util.get_next_subnet())
    zones = network.zones()

    ssh_pub_key = SSHUtil().get_ssh_public_key(aws_parameters.get("ssh_key"))

    vpc_id = network.create(vpc_name, vpc_cidr)
    cleanup(lambda: network.delete(vpc_id))

    sg_id = sg.create(sg_name, "pytest instance sg", vpc_id)
    cleanup(lambda: sg.delete(sg_id))

    ssh_key_name = ssh.create(key_name, ssh_pub_key)
    cleanup(lambda: ssh.delete(ssh_key_name))

    subnet_id = subnet_drv.create(subnet_name, vpc_id, zones[0], subnet_cidr)
    cleanup(lambda: subnet_drv.delete(subnet_id))

    ig_id = gateway.create(ig_name, vpc_id)
    cleanup(lambda: gateway.delete(ig_id))

    rt_id = route.create(rt_name, vpc_id)
    cleanup(lambda: route.delete(rt_id))
    route.add_route("0.0.0.0/0", ig_id, rt_id)
    route.associate(rt_id, subnet_id)

    image = Image(aws_parameters).list_standard(os_id="ubuntu", os_version="22.04", architecture="x86_64")

    instance_id = instance.run(
        name=node_name,
        ami=image["name"],
        ssh_key=ssh_key_name,
        sg_list=sg_id,
        subnet=subnet_id,
        zone=zones[0],
        instance_type="t3.micro",
        root_size=8,
        swap_size=1,
        data_size=1,
        tags=parameter_to_dict(aws_parameters.get("tags")),
    )
    cleanup(lambda: instance.terminate(instance_id))

    details = instance.details(instance_id)
    assert details is not None
    assert details["InstanceId"] == instance_id

    listed = instance.list()
    assert any(item["InstanceId"] == instance_id for item in listed)

    instance.terminate(instance_id)
    details = instance.details(instance_id)
    assert details is not None
    assert details.get('State', {}).get('Name') == "terminated"
