import os

_ROOT = os.path.abspath(os.path.dirname(__file__))
__version__ = "5.0.0a1"
VERSION = __version__


def get_data_dir():
    return os.path.join(_ROOT, 'data')
