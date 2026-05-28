import os

_ROOT = os.path.abspath(os.path.dirname(__file__))
__version__ = "4.1.0"
VERSION = __version__


def get_data_dir():
    return os.path.join(_ROOT, 'data')
