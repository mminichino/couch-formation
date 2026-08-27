##
##

import logging
import os
import secrets
import couchformation.constants as C
import couchformation.kvdb as kvdb
from couchformation.config import get_root_dir
from couchformation.exception import FatalError
from couchformation.util import FileManager
from couchformation.kvdb import KeyValueStore

logger = logging.getLogger('couchformation.config.manager')
logger.addHandler(logging.NullHandler())


class ConfigError(FatalError):
    pass


PARAMETERS = {
    'aws.tags': {
        'type': 'string',
        'mutable': True
    },
    'tags': {
        'type': 'string',
        'mutable': True
    },
    'capella.token': {
        'type': 'string',
        'mutable': True
    },
    'capella.user': {
        'type': 'string',
        'mutable': True
    },
    'capella.user.id': {
        'type': 'string',
        'mutable': True
    },
    'capella.project': {
        'type': 'string',
        'mutable': True
    },
    'capella.project.id': {
        'type': 'string',
        'mutable': True
    },
    "ssh.key": {
        'type': 'string',
        'mutable': True
    },
    "aws.domain": {
        'type': 'string',
        'mutable': True
    },
    "gcp.domain": {
        'type': 'string',
        'mutable': True
    },
    "azure.domain": {
        'type': 'string',
        'mutable': True
    },
    "api.token": {
        'type': 'string',
        'mutable': True
    },
}


class ConfigurationManager(object):

    def __init__(self):
        self.filename = os.path.join(get_root_dir(), "cf.db")
        legacy = os.path.join(get_root_dir(), "config.db")

        try:
            if not os.path.exists(get_root_dir()):
                FileManager().make_dir(get_root_dir())
            if not os.path.exists(self.filename) and os.path.exists(legacy):
                self.filename = legacy
            elif not os.path.exists(self.filename) and os.path.exists(C.LEGACY_CONFIG_FILE) and get_root_dir() == C.ROOT_DIRECTORY:
                self.filename = C.LEGACY_CONFIG_FILE
        except Exception as err:
            raise ConfigError(f"can not create root dir: {err}")

    @staticmethod
    def key_split(key: str):
        vector = key.split('.', 1)
        if len(vector) != 2:
            raise ConfigError(f"Malformed key {key}")

        table_name = vector[0]
        value_name = vector[1]

        return table_name, value_name

    @staticmethod
    def strtobool(val):
        val = val.lower()
        if val in ('y', 'yes', 't', 'true', 'on', '1'):
            return 1
        elif val in ('n', 'no', 'f', 'false', 'off', '0'):
            return 0
        else:
            raise ValueError(f"invalid truth value {val}")

    def convert(self, key, value):
        key_settings = PARAMETERS.get(key)
        if key_settings is None:
            raise ConfigError(f"Configuration key {key} not supported")

        try:
            if key_settings['type'] == 'string':
                return str(value)
            elif key_settings['type'] == 'integer':
                return int(value)
            elif key_settings['type'] == 'boolean':
                return bool(self.strtobool(value))
            elif key_settings['type'] == 'decimal':
                return float(value)
        except ValueError as e:
            raise ConfigError(f"Invalid value {value} for key {key} of type {value}: {e}")

    @staticmethod
    def mutable(key: str):
        key_settings = PARAMETERS.get(key)
        if key_settings is None:
            raise ConfigError(f"Configuration key {key} not supported")
        return key_settings['mutable']

    def get(self, key: str):
        if key not in PARAMETERS:
            raise ConfigError(f"Configuration parameter {key} not supported")

        table_name, value_name = self.key_split(key)

        table = KeyValueStore(self.filename, table_name)
        if table.get(value_name):
            return self.convert(key, table.get(value_name))
        else:
            return None

    def set(self, key: str, value: str):
        if key not in PARAMETERS:
            raise ConfigError(f"Configuration parameter {key} not supported")
        if not self.mutable(key):
            raise ConfigError(f"Configuration key {key} is not mutable")

        table_name, value_name = self.key_split(key)

        table = KeyValueStore(self.filename, table_name)
        table[value_name] = self.convert(key, value)

    def delete(self, key: str):
        if key not in PARAMETERS:
            raise ConfigError(f"Configuration parameter {key} not supported")
        if not self.mutable(key):
            raise ConfigError(f"Configuration key {key} is not mutable")

        table_name, value_name = self.key_split(key)

        table = KeyValueStore(self.filename, table_name)
        if table.get(value_name):
            del table[value_name]

    def reset(self):
        for table in kvdb.documents(self.filename):
            table.clear()

    def list(self):
        response = {}
        for key in PARAMETERS.keys():
            table_name, value_name = self.key_split(key)
            table = KeyValueStore(self.filename, table_name)
            if table.get(value_name):
                response[key] = self.convert(key, table.get(value_name))
        return response

    def ensure_api_token(self, token: str | None = None) -> str:
        existing = self.get('api.token')
        if token:
            self.set('api.token', token)
            return token
        if existing:
            return existing
        generated = secrets.token_urlsafe(32)
        self.set('api.token', generated)
        return generated
