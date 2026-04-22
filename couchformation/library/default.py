##
##

from typing import Optional
from couchformation.library.profile import ProfileClass


class Default(ProfileClass):
    """Default instance profile.

    Accepted options:
        --type      <type>          Node / instance type string.
        --services  <service_list>  Comma-separated list of services to configure.
    """

    name = "default"
    description = "Default instance profile"

    def apply(
        self,
        group_name: str,
        type: Optional[str] = None,
        services: Optional[str] = None,
    ) -> None:
        pass
