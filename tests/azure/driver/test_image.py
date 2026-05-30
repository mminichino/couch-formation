from __future__ import annotations

import pytest

from couchformation.azure.driver.image import Image

pytestmark = pytest.mark.cf_azure


def test_list_standard_returns_ubuntu_image(azure_parameters):
    image = Image(azure_parameters)
    result = image.list_standard(os_id="ubuntu", os_version="22.04")
    assert result is not None
    assert result["os_id"] == "ubuntu"
    assert result["os_version"] == "22.04"
    assert result["publisher"]
    assert result["offer"]
    assert result["sku"]
