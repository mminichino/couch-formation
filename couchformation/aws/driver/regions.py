##
##

from couchformation.aws.driver.base import CloudBase


class Regions(CloudBase):

    def get_all_regions(self) -> list:
        regions = self.ec2_client.describe_regions(AllRegions=False)
        region_list = list(r['RegionName'] for r in regions['Regions'])
        return region_list
