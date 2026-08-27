from __future__ import annotations

import pytest

from couchformation.gcp.driver.image import Image

pytestmark = [pytest.mark.driver, pytest.mark.cf_gcp]



def test_list_standard_returns_ubuntu_image(gcp_parameters):
    image = Image(gcp_parameters)
    result = image.list_standard(os_id="ubuntu", os_version="22.04")
    assert result is not None
    assert result["os_id"] == "ubuntu"
    assert result["os_version"] == "22.04"
    assert result["name"]
    assert result["image_project"]


def test_details_returns_image(gcp_parameters):
    image = Image(gcp_parameters)
    standard = image.list_standard(os_id="ubuntu", os_version="22.04")
    details = image.details(standard["name"], standard["image_project"])
    assert details is not None
    assert details["name"] == standard["name"]
