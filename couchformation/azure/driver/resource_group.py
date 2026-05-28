##
##

from typing import List, Union

from couchformation.azure.driver.base import CloudBase, AzureDriverError, EmptyResultSet


class ResourceGroup(CloudBase):

    def create_rg(self, name: str, location: str, tags: Union[dict, None] = None) -> dict:
        if not tags:
            tags = {}
        if not tags.get('type'):
            tags.update({"type": "couch-formation"})
        try:
            if self.resource_client.resource_groups.check_existence(name):
                return self.get_rg(name, location)
            else:
                result = self.resource_client.resource_groups.create_or_update(
                    name,
                    {
                        "location": location,
                        "tags": tags
                    }
                )
                return result.__dict__
        except Exception as err:
            raise AzureDriverError(f"error creating resource group: {err}")

    def get_rg(self, name: str, location: str) -> Union[dict, None]:
        try:
            if self.resource_client.resource_groups.check_existence(name):
                result = self.resource_client.resource_groups.get(name)
                if result.location == location:
                    return result.__dict__
        except Exception as err:
            raise AzureDriverError(f"error getting resource group: {err}")

        return None

    def list_rg(self, location: Union[str, None] = None, filter_keys_exist: Union[List[str], None] = None) -> List[dict]:
        rg_list = []

        try:
            resource_groups = self.resource_client.resource_groups.list()
        except Exception as err:
            raise AzureDriverError(f"error getting resource groups: {err}")

        for group in list(resource_groups):
            if location:
                if group.location != location:
                    continue
            rg_block = {'location': group.location,
                        'name': group.name,
                        'id': group.id}
            rg_block.update(self.process_tags(group.tags))
            if filter_keys_exist:
                if not all(key in rg_block for key in filter_keys_exist):
                    continue
            rg_list.append(rg_block)

        if len(rg_list) == 0:
            raise EmptyResultSet(f"no resource groups found")

        return rg_list

    def delete_rg(self, name: str):
        try:
            if self.resource_client.resource_groups.check_existence(name):
                request = self.resource_client.resource_groups.begin_delete(name)
                request.wait()
        except Exception as err:
            raise AzureDriverError(f"error deleting resource group: {err}")

    def rg_switch(self):
        image_rg = f"cf-image-{self.azure_location}-rg"
        if self.get_rg(image_rg, self.azure_location):
            resource_group = image_rg
        else:
            resource_group = self.azure_resource_group
        return resource_group
