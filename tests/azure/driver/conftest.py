from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest

from couchformation.network import NetworkDriver
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.identity.id import UniqueId

UUID: UniqueId = UniqueId()


@pytest.fixture(autouse=True)
def _neutralize_fatal_error(monkeypatch):
    import couchformation.exception as exc_mod

    def _init(self, message):
        Exception.__init__(self, message)
        self.message = message

    monkeypatch.setattr(exc_mod.FatalError, "__init__", _init)
    yield


@pytest.fixture(scope="module")
def azure_parameters():
    cm = ConfigurationManager()
    params = {
        "cloud": "azure",
        "region": "eastus",
        "project": f"pytest-azure-driver-{uuid.uuid4().hex[:8]}",
    }
    if cm.get("ssh.key"):
        params["ssh_key"] = cm.get("ssh.key")
    return params


@pytest.fixture
def cleanup(request):
    handlers: list[Callable[[], None]] = []

    def register(fn: Callable[[], None]) -> None:
        handlers.append(fn)

    def _run_cleanup() -> None:
        for fn in reversed(handlers):
            try:
                fn()
            except Exception:
                pass

    request.addfinalizer(_run_cleanup)
    return register


@pytest.fixture
def cidr_util(azure_parameters):
    util = NetworkDriver()
    from couchformation.azure.driver.network import Network

    for net in Network(azure_parameters).cidr_list:
        util.add_network(net)
    return util


def unique_name(prefix: str) -> str:
    return f"{prefix}-{UUID.short}"


def domain_name() -> str:
    cm = ConfigurationManager()
    if cm.get("azure.domain"):
        return f"{UUID.min}.{cm.get('azure.domain')}"
    else:
        return f"{UUID.min}.example.com"


@pytest.fixture(scope="module")
def azure_rg(azure_parameters):
    from couchformation.azure.driver.resource_group import ResourceGroup

    rg = ResourceGroup(azure_parameters)
    rg_name = f"{azure_parameters['project']}-rg"
    rg.create_rg(rg_name, azure_parameters["region"])
    yield rg_name
    try:
        rg.delete_rg(rg_name)
    except Exception:
        pass
