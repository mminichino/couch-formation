from __future__ import annotations

import pytest

from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.disk import Disk
from couchformation.gcp.driver.firewall import Firewall
from couchformation.gcp.driver.image import Image
from couchformation.gcp.driver.instance import Instance
from couchformation.gcp.driver.machine import MachineType
from couchformation.gcp.driver.network import Network
from couchformation.gcp.driver.subnet import Subnet
from couchformation.ssh import SSHUtil
from tests.gcp.driver.conftest import unique_name

pytestmark = pytest.mark.cf_gcp


def test_instance_run_terminate(gcp_parameters, cidr_util, cleanup):
    base = CloudBase(gcp_parameters)
    network = Network(gcp_parameters)
    subnet_drv = Subnet(gcp_parameters)
    firewall = Firewall(gcp_parameters)
    disk = Disk(gcp_parameters)
    instance = Instance(gcp_parameters)

    vpc_name = unique_name(f"{gcp_parameters['project']}-vpc")
    subnet_name = unique_name(f"{gcp_parameters['project']}-subnet")
    fw_name = unique_name(f"{gcp_parameters['project']}-fw")
    swap_disk = unique_name(f"{gcp_parameters['project']}-swap")
    data_disk = unique_name(f"{gcp_parameters['project']}-data")
    node_name = unique_name(f"{gcp_parameters['project']}-node")

    zone = base.zones()[0]
    subnet_cidr = next(cidr_util.get_next_subnet())
    vpc_cidr = cidr_util.get_next_network()
    ssh_pub_key = SSHUtil().get_ssh_public_key(gcp_parameters.get("ssh_key"))

    network.create(vpc_name)
    cleanup(lambda: network.delete(vpc_name))

    subnet_drv.create(subnet_name, vpc_name, subnet_cidr)
    cleanup(lambda: subnet_drv.delete(subnet_name))

    firewall.create_ingress(fw_name, vpc_name, vpc_cidr, "tcp", ["22"])
    cleanup(lambda: firewall.delete(fw_name))

    disk.create(swap_disk, zone, "4")
    cleanup(lambda: disk.delete(swap_disk, zone))
    disk.create(data_disk, zone, "10")
    cleanup(lambda: disk.delete(data_disk, zone))

    image = Image(gcp_parameters).list_standard(os_id="ubuntu", os_version="22.04")
    machine = MachineType(gcp_parameters).get_machine("2x8", zone)

    instance.run(
        node_name,
        image["image_project"],
        image["name"],
        base.service_account_email,
        zone,
        vpc_name,
        subnet_name,
        image["os_user"],
        ssh_pub_key,
        swap_disk,
        data_disk,
        machine_type=machine["name"],
        root_size="10",
    )
    cleanup(lambda: instance.terminate(node_name, zone))

    assert instance.find(node_name) is not None
    assert instance.details(node_name, zone) is not None

    instance.terminate(node_name, zone)
    assert instance.find(node_name) is None
