import logging
import json
import warnings
import unittest
import pytest

from couchformation.aws.driver.auth import AWSAuth

warnings.filterwarnings("ignore")
logger = logging.getLogger('couchformation.tests.aws')


@pytest.mark.cf_aws
@pytest.mark.order(1)
class TestAWSAuth(unittest.TestCase):

    def test_1(self):
        auth = AWSAuth()

        auth.test_session()

        zone_list = auth.zones()
        auth_config = auth.get_auth_config()

        for zone in zone_list:
            logger.info(zone)

        logger.info(f"AWS Auth Config:\n{json.dumps(auth_config, indent=4)}")
