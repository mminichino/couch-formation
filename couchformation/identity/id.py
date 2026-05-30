##
##

import hashlib
import uuid

class UniqueId:

    def __init__(self):
        self._uuid = uuid.uuid4()

    @property
    def uuid(self) -> str:
        return str(self._uuid)

    @property
    def short(self) -> str:
        return hashlib.md5(str(self._uuid).encode()).hexdigest()[:16]

    @property
    def min(self) -> str:
        digest = hashlib.md5(str(self._uuid).encode()).digest()
        return ''.join(chr(ord('a') + (b % 26)) for b in digest[:8])
