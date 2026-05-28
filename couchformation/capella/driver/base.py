##
##

import logging
from couchformation.exception import FatalError
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.models.cloud_auth import CapellaCredentials, CloudLoginParameters
from couchformation.models.public_cloud import PublicCloud
from libcapella.config import CapellaConfig
from libcapella.organization import CapellaOrganization
from libcapella.project import CapellaProject
from libcapella.logic.project import CapellaProjectBuilder

logger = logging.getLogger('couchformation.capella.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("restfull").setLevel(logging.ERROR)


class CapellaDriverError(FatalError):
    pass


class CloudBase(PublicCloud):

    def __init__(self, parameters: dict | CloudLoginParameters | None = None):
        self.parameters: dict = {}
        self._token = None
        self._account_email = None
        self._account_id = None
        self._project_name = None
        self._region = None
        self.org = None
        self._project = None

        if parameters is not None:
            login_params = CloudLoginParameters.from_parameters(parameters)
            self.parameters = login_params.model_dump(exclude_none=True)
            self.login(login_params)

    def login(self, parameters: CloudLoginParameters) -> None:
        self.parameters = parameters.model_dump(exclude_none=True)

        cm = ConfigurationManager()
        if cm.get('capella.token'):
            self._token = cm.get('capella.token')
        if cm.get('capella.user'):
            self._account_email = cm.get('capella.user')
        if cm.get('capella.user.id'):
            self._account_id = cm.get('capella.user.id')
        if cm.get('capella.project'):
            self._project_name = cm.get('capella.project')
        elif parameters.project:
            self._project_name = parameters.project
        else:
            self._project_name = self.parameters.get('project')

        if parameters.region:
            self._region = parameters.region
        else:
            self._region = self.parameters.get('region')

        try:
            if self._token and (self._account_email or self._account_id):
                config_dict = {
                    "token": self._token,
                    "account_email": self._account_email,
                    "project_name": self._project_name,
                    "account_id": self._account_id,
                }
                logger.debug(f"Capella config parameters: {config_dict}")
                config = CapellaConfig(config_dict=config_dict)
            else:
                profile = parameters.profile or self.parameters.get('profile')
                logger.debug(f"Capella credential profile: {profile}")
                config = CapellaConfig(profile=profile)

            self._token = config.config.token
            self._account_email = config.config.account_email

            if not self._account_email:
                raise CapellaDriverError("Capella account email not set")

            if not self._token:
                raise CapellaDriverError("Capella v4 API token not set")

            self.org = CapellaOrganization(config)
            self._project = CapellaProject(self.org, self._project_name, self._account_email)
            if not self._project.id:
                logger.info(f"Creating project {self._project_name}")
                builder = CapellaProjectBuilder()
                builder = builder.name(self._project_name)
                config = builder.build()
                self._project.create(config)
        except Exception as err:
            raise CapellaDriverError(f"can not access Capella project {self._project_name}: {err}")

    def test_session(self):
        try:
            self.org.list()
        except Exception as err:
            raise CapellaDriverError(f"not authorized: {err}")

    def credentials(self) -> CapellaCredentials:
        return CapellaCredentials(
            token=self._token,
            user=self._account_email,
            user_id=self._account_id,
            project=self._project_name,
        )

    def zones(self) -> list:
        if self._region:
            return [self._region]
        return []

    def get_region(self) -> str | None:
        return self._region

    def set_region(self, region: str) -> None:
        self._region = region

    @property
    def project_id(self):
        return self._project.id

    @property
    def organization_id(self):
        return self.org.id

    @property
    def project_name(self):
        return self._project_name

    @property
    def project(self):
        return self._project
