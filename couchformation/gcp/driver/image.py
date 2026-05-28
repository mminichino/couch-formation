##
##

import logging
import re
from datetime import datetime
from typing import List, Union

from google.api_core import exceptions as gcp_exceptions

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet, resource_to_dict
from couchformation.gcp.driver.constants import GCPImageProjects
import couchformation.constants as C

logger = logging.getLogger('couchformation.gcp.driver.image')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class Image(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, project: Union[str, None] = None, architecture: str = 'x86-64') -> List[dict]:
        image_list = []
        if not project:
            project = self.gcp_project

        try:
            for image in self.image_client.list(project=project):
                image_data = resource_to_dict(image)
                if 'deprecated' in image_data:
                    state = image_data['deprecated'].get('state')
                    if state in ("DEPRECATED", "OBSOLETE"):
                        continue
                _image_is_arm = re.search('arm64', image_data['name'])
                if architecture == 'arm64' and not _image_is_arm:
                    continue
                elif _image_is_arm:
                    continue
                image_block = {
                    'name': image_data['name'],
                    'link': image_data['selfLink'],
                    'date': image_data['creationTimestamp'],
                }
                image_block.update(self.process_labels(image_data))
                image_list.append(image_block)
        except Exception as err:
            raise GCPDriverError(f"error getting images: {err}")

        if len(image_list) == 0:
            raise EmptyResultSet("no images found")

        return image_list

    def details(self, image: str, project: Union[str, None] = None) -> dict:
        if not project:
            project = self.gcp_project

        try:
            result = self.image_client.get(project=project, image=image)
            image_data = resource_to_dict(result)
        except gcp_exceptions.NotFound:
            raise EmptyResultSet(f"image {image} not found")
        except Exception as err:
            raise GCPDriverError(f"image detail error: {err}")

        image_block = {
            'name': image_data['name'],
            'link': image_data['selfLink'],
            'date': image_data['creationTimestamp'],
        }
        image_block.update(self.process_labels(image_data))

        return image_block

    def delete(self, image: str) -> None:
        try:
            operation = self.image_client.delete(project=self.gcp_project, image=image)
            self.wait_for_global_operation(operation.name)
        except Exception as err:
            raise GCPDriverError(f"error deleting image: {err}")

    def list_standard(self, architecture: str = 'x86_64', os_id: str = None, os_version: str = None):
        result_list = []
        for image_type in GCPImageProjects.projects:
            if os_id and image_type['os_id'] != os_id:
                continue
            image_list = self.list(project=image_type['project'], architecture=architecture)
            for version in C.OS_VERSION_LIST[image_type['os_id']]:
                if os_version and version != os_version:
                    continue
                filtered_images = []
                for image in image_list:
                    logger.debug(f"Found image -> {image['name']}")
                    match = re.search(image_type['pattern'], image['name'])
                    if match and (match.group(1) == version or match.group(1) == ''.join([letter for letter in '22.04' if letter.isalnum()])):
                        filtered_images.append(image)
                if len(filtered_images) > 0:
                    filtered_images.sort(key=lambda i: datetime.fromisoformat(i['date']))
                    result_image = filtered_images[-1]
                    result_image.update(dict(
                        os_id=image_type['os_id'],
                        os_version=version,
                        os_user=image_type['user'],
                        image_project=image_type['project']
                    ))
                    result_list.append(result_image)
                if len(result_list) > 0:
                    logger.debug(f"Selected image -> {result_list[-1]}")
                return result_list[-1]

    @staticmethod
    def image_user(os_id: str):
        return next((image_type['user'] for image_type in GCPImageProjects.projects if image_type['os_id'] == os_id), None)
