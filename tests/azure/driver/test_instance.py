from __future__ import annotations

import pytest

from couchformation.azure.driver.disk import Disk
from couchformation.azure.driver.image import Image
from couchformation.azure.driver.instance import Instance
from couchformation.azure.driver.machine import MachineType
from couchformation.azure.driver.network import Network, SecurityGroup, Subnet
from couchformation.azure.driver.resource_group import ResourceGroup
from couchformation.ssh import SSHUtil
from tests.azure.driver.conftest import unique_name

pytestmark = pytest.mark.cf_azure


def test_instance_run_terminate(azure_parameters, azure_rg, cidr_util, cleanup):
    base = ResourceGroup(azure_parameters)
    network = Network(azure_parameters)
    subnet_drv = Subnet(azure_parameters)
    nsg = SecurityGroup(azure_parameters)
    disk = Disk(azure_parameters)
    instance = Instance(azure_parameters)

    vpc_name = unique_name(f"{azure_parameters['project']}-vpc")
    nsg_name = unique_name(f"{azure_parameters['project']}-nsg")
    subnet_name = unique_name(f"{azure_parameters['project']}-subnet")
    node_name = unique_name(f"{azure_parameters['project']}-node")
    boot_disk = unique_name(f"{azure_parameters['project']}-boot")
    node_pub_ip = unique_name(f"{azure_parameters['project']}-ip")
    node_nic = unique_name(f"{azure_parameters['project']}-nic")

    vpc_cidr = cidr_util.get_next_network()
    subnet_cidr = next(cidr_util.get_next_subnet())
    zone = base.zones()[0]
    ssh_pub_key = SSHUtil().get_ssh_public_key(azure_parameters.get("ssh_key"))

    network.create(vpc_name, vpc_cidr, azure_rg)
    cleanup(lambda: network.delete(vpc_name, azure_rg))

    nsg_resource = nsg.create(nsg_name, azure_rg)
    cleanup(lambda: nsg.delete(nsg_name, azure_rg))
    nsg.add_rule("AllowSSH", nsg_name, ["22"], 100, azure_rg)

    subnet_resource = subnet_drv.create(subnet_name, vpc_name, subnet_cidr, nsg_resource.id, azure_rg)
    cleanup(lambda: subnet_drv.delete(vpc_name, subnet_name, azure_rg))

    pub_ip = network.create_pub_ip(node_pub_ip, azure_rg)
    cleanup(lambda: network.delete_pub_ip(node_pub_ip, azure_rg))

    nic = network.create_nic(node_nic, subnet_resource.id, zone, pub_ip.id, azure_rg)
    cleanup(lambda: network.delete_nic(node_nic, azure_rg))

    image = Image(azure_parameters).list_standard(os_id="ubuntu", os_version="22.04")
    machine = MachineType(azure_parameters).get_machine("2x8", azure_parameters["region"])

    instance.run(
        node_name,
        image["publisher"],
        image["offer"],
        image["sku"],
        zone,
        nic.id,
        image["os_user"],
        ssh_pub_key,
        azure_rg,
        boot_disk,
        machine_type=machine["name"],
        root_size=32,
    )
    cleanup(lambda: instance.terminate(node_name, azure_rg))
    cleanup(lambda: disk.delete(boot_disk, azure_rg))

    details = instance.details(node_name, azure_rg)
    assert details is not None
    assert details.name == node_name

    instance.terminate(node_name, azure_rg)
    assert instance.details(node_name, azure_rg) is None
