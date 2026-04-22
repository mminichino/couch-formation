##
##

from abc import ABC, abstractmethod
from typing import Any


class ProfileClass(ABC):
    """Base class for all instance profiles.

    Subclasses define their own CLI options and implement the apply
    method.  The apply method receives the target group name plus any
    profile-specific keyword arguments parsed from the command line.
    """

    #: Human-readable name shown in help text.
    name: str = ""

    #: One-line description shown in help text.
    description: str = ""

    @abstractmethod
    def apply(self, group_name: str, **kwargs: Any) -> None:
        """Apply the profile to *group_name*.

        Subclasses receive profile-specific CLI values as *kwargs*.
        """
        raise NotImplementedError
