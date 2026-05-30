from __future__ import annotations

import pytest

from couchformation.aws.driver.image import Image

pytestmark = pytest.mark.cf_aws


def test_list_standard_returns_ubuntu_image(aws_parameters):
    image = Image(aws_parameters)
    result = image.list_standard(os_id="ubuntu", os_version="22.04", architecture="x86_64")
    assert result is not None
    assert result["os_id"] == "ubuntu"
    assert result["os_version"] == "22.04"
    assert result["name"]
    assert result["os_user"] == "ubuntu"


def test_list_public_images(aws_parameters):
    image = Image(aws_parameters)
    result = image.list(is_public=True, owner_id="099720109477", name="ubuntu/images/hvm-ssd/ubuntu-*-server-*")
    assert len(result) > 0
    assert result[0]["name"]
    assert result[0]["arch"]


def test_image_user_known_id():
    assert Image.image_user("ubuntu") == "ubuntu"


def test_details_returns_image(aws_parameters):
    image = Image(aws_parameters)
    standard = image.list_standard(os_id="ubuntu", os_version="22.04", architecture="x86_64")
    details = image.details(standard["name"])
    assert details is not None
    assert details["ImageId"] == standard["name"]
