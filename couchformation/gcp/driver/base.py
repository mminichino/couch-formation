##
##

import os.path
import socket
import logging
import json
import base64
import sqlite3
import google.auth
import google.auth.transport.requests
from pathlib import Path
from google.cloud import compute_v1
from google.cloud import storage
from google.cloud import dns
from google.oauth2 import service_account
from google.cloud import resourcemanager_v3
from google.oauth2.credentials import Credentials

from couchformation.gcp.driver.constants import get_auth_directory, get_default_credentials
from couchformation.gcp.driver.operations import (
    GCPDriverError,
    GCPDriverTransientError,
    GCPOperations,
)
from couchformation.models.cloud_auth import CloudLoginParameters, GCPCredentials
from couchformation.models.public_cloud import PublicCloud
from couchformation.retry import retry

logger = logging.getLogger('couchformation.gcp.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class CloudBase(GCPOperations, PublicCloud):

    def __init__(self, parameters: dict | CloudLoginParameters | None = None):
        self.parameters: dict = {}
        self.auth_directory = get_auth_directory()
        self.gcp_project = None
        self.gcp_region = None
        self._service_account_email = None
        self._user_account_email = None
        self.gcp_zone_list = []
        self.gcp_zone = None
        self.credentials: Credentials | None = None
        self.instance_client = None
        self.disk_client = None
        self.dns_client = None
        self.image_client = None
        self.machine_type_client = None
        self.subnetwork_client = None
        self.network_client = None
        self.firewall_client = None
        self.zones_client = None
        self.global_operations_client = None
        self.region_operations_client = None
        self.zone_operations_client = None

        socket.setdefaulttimeout(120)

        if parameters is not None:
            login_params = CloudLoginParameters.from_parameters(parameters)
            self.parameters = login_params.model_dump(exclude_none=True)
            self.login(login_params)

    def login(self, parameters: CloudLoginParameters) -> None:
        self.parameters = parameters.model_dump(exclude_none=True)

        if parameters.project:
            self.gcp_project = parameters.project

        try:
            self.instance_client = compute_v1.InstancesClient()
            self.firewall_client = compute_v1.FirewallsClient()
            self.network_client = compute_v1.NetworksClient()
            self.subnetwork_client = compute_v1.SubnetworksClient()
            self.machine_type_client = compute_v1.MachineTypesClient()
            self.image_client = compute_v1.ImagesClient()
            self.disk_client = compute_v1.DisksClient()
            self.zones_client = compute_v1.ZonesClient()
            self.global_operations_client = compute_v1.GlobalOperationsClient()
            self.region_operations_client = compute_v1.RegionOperationsClient()
            self.zone_operations_client = compute_v1.ZoneOperationsClient()
            self.dns_client = dns.Client()
            self.credentials, self.gcp_project = google.auth.default()
        except Exception as e:
            raise GCPDriverError(f"Failed to initialize GCP client: {e}")

        if not self.gcp_project:
            raise GCPDriverError("can not determine GCP project")

        if parameters.region:
            self.set_region(parameters.region)
        elif self.parameters.get('region'):
            self.set_region(self.parameters['region'])
        else:
            raise GCPDriverError("region not specified")

        try:
            self.zones()
        except GCPDriverTransientError:
            raise GCPDriverError(
                "There is likely an auth config or firewall problem - make sure you can access "
                "the GCP API and use \"gcloud auth\" to configure access"
            )
        except Exception as err:
            raise GCPDriverError(f"error getting availability zones: {err}")

    def test_session(self):
        try:
            storage_client = storage.Client(
                project=self.gcp_project,
                credentials=self.credentials,
            )
            storage_client.list_buckets()
        except Exception as err:
            raise GCPDriverError(f"not authorized: {err}")

    def credentials(self) -> GCPCredentials:
        return GCPCredentials(
            account_email=self.account_email,
            project_id=self.gcp_project,
            project_number=self.project_number,
            default_service_account=self.default_sa,
        )

    def get_account_email(self):
        try:
            if hasattr(self.credentials, "service_account_email"):
                service_account_email = self.credentials.service_account_email
                account_email = None
            elif hasattr(self.credentials, "signer_email"):
                service_account_email = self.credentials.signer_email
                account_email = None
            else:
                service_account_email = None
                request = google.auth.transport.requests.Request()
                self.credentials.refresh(request=request)
                token_payload = self.credentials.id_token.split('.')[1]
                input_bytes = token_payload.encode('utf-8')
                rem = len(input_bytes) % 4
                if rem > 0:
                    input_bytes += b"=" * (4 - rem)
                json_data = base64.urlsafe_b64decode(input_bytes).decode('utf-8')
                token_data = json.loads(json_data)
                account_email = token_data.get('email')
            return service_account_email, account_email
        except Exception as err:
            raise GCPDriverError(f"error getting GCP account email: {err}")

    @staticmethod
    def get_config_dir():
        if 'CLOUDSDK_CONFIG' in os.environ:
            return os.environ['CLOUDSDK_CONFIG']
        if os.name != 'nt':
            return os.path.join(Path.home(), '.config', 'gcloud')
        if 'APPDATA' in os.environ:
            return os.path.join(os.environ['APPDATA'], 'gcloud')
        drive = os.environ.get('SystemDrive', 'C:')
        return os.path.join(drive, os.path.sep, 'gcloud')

    def get_account(self, account: str):
        account_db = os.path.join(self.get_config_dir(), 'credentials.db')
        connection = sqlite3.connect(
            account_db,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None,
            check_same_thread=True
        )

        cursor = connection.cursor()
        table = cursor.execute('SELECT account_id, value FROM credentials').fetchall()
        for row in table:
            account_id, cred_json = row[0], row[1]
            if account_id == account:
                return json.loads(cred_json)

        return None

    def sa_auth(self, service_account_email):
        auth_data = self.get_account(service_account_email)
        if not auth_data:
            raise GCPDriverError(
                f"Account {service_account_email} is not configured. Use gcloud auth to add the account."
            )
        credentials, _ = google.auth.load_credentials_from_dict(auth_data)
        return credentials

    @property
    def project_number(self):
        rm = resourcemanager_v3.ProjectsClient()
        req = resourcemanager_v3.GetProjectRequest(dict(name=f"projects/{self.gcp_project}"))
        res = rm.get_project(request=req)
        project_number = res.name.split('/')[1]
        return project_number

    @property
    def default_sa(self):
        return f"{self.project_number}-compute@developer.gserviceaccount.com"

    def file_auth(self):
        auth_file = get_default_credentials()
        if os.path.exists(auth_file):
            credentials = service_account.Credentials.from_service_account_file(auth_file)
            auth_data = self.read_auth_file(auth_file)
            project_id = auth_data.get('project_id')
            account_email = auth_data.get('client_email')
            return credentials, project_id, account_email
        else:
            raise GCPDriverError("file auth selected: can not find application_default_credentials.json")

    @staticmethod
    def read_auth_file(auth_file: str):
        file_handle = open(auth_file, 'r')
        auth_data = json.load(file_handle)
        file_handle.close()
        return auth_data

    @retry()
    def zones(self) -> list:
        try:
            for zone in self.zones_client.list(project=self.gcp_project):
                if zone.name.startswith(self.gcp_region):
                    self.gcp_zone_list.append(zone.name)
        except Exception as err:
            raise GCPDriverTransientError(f"error getting zones: {err}")

        self.gcp_zone_list = sorted(set(self.gcp_zone_list))

        if len(self.gcp_zone_list) == 0:
            raise GCPDriverError("can not get GCP availability zones")

        self.gcp_zone = self.gcp_zone_list[0]
        return self.gcp_zone_list

    def get_region(self) -> str | None:
        return self.gcp_region

    def set_region(self, region: str) -> None:
        self.gcp_region = region
        self.gcp_zone_list = []
        self.gcp_zone = None

    @property
    def region(self):
        return self.get_region()

    @property
    def project(self):
        return self.gcp_project

    @property
    def service_account_email(self):
        return self._service_account_email

    @property
    def login_account_email(self):
        return self._user_account_email

    @property
    def account_email(self):
        return self._service_account_email if self._service_account_email else self._user_account_email

    @staticmethod
    def process_labels(struct: dict) -> dict:
        block = {}
        if 'labels' in struct:
            for tag in struct['labels']:
                block.update({tag.lower() + '_tag': struct['labels'][tag]})
        block = dict(sorted(block.items()))
        return block
