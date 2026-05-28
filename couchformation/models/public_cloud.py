from abc import ABC, abstractmethod

from couchformation.models.cloud_auth import CloudCredentials, CloudLoginParameters


class PublicCloud(ABC):

    @abstractmethod
    def login(self, parameters: CloudLoginParameters) -> None:
        pass

    @abstractmethod
    def test_session(self) -> None:
        pass

    @abstractmethod
    def zones(self) -> list:
        pass

    @abstractmethod
    def get_region(self) -> str | None:
        pass

    @abstractmethod
    def set_region(self, region: str) -> None:
        pass

    @abstractmethod
    def credentials(self) -> CloudCredentials:
        pass
