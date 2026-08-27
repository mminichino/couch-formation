##

from typing import Union, List
from pathlib import Path
from Crypto.Cipher import AES
from Crypto import Random
from hashlib import sha256
import string
import random
import base64
import hashlib
import io
import os
import tarfile
import warnings
import logging
import subprocess
import configparser

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
logger = logging.getLogger('tests.common')
logger.addHandler(logging.NullHandler())
logging.getLogger("urllib3").setLevel(logging.WARNING)

ssh_key_path = os.path.join(Path.home(), '.ssh', 'pytest-key-pair.pem')
ssh_pub_key_path = os.path.join(Path.home(), '.ssh', 'pytest-key-pair.pub')
ssh_key_relative_path = os.path.relpath(ssh_key_path, Path.home())
ssh_pub_key_relative_path = os.path.relpath(ssh_pub_key_path, Path.home())
capella_config_path = os.path.join(Path.home(), '.capella')
capella_config_relative_path = os.path.relpath(capella_config_path, Path.home())
aws_config_dir = os.path.join(Path.home(), '.aws')
gcp_config_dir = os.path.join(Path.home(), '.config', 'gcloud')
azure_config_dir = os.path.join(Path.home(), '.azure')
local_config_file = os.path.join(Path.home(), '.config', 'couch-formation', 'local.conf')
if os.name == 'nt':
    WINDOWS = True
else:
    WINDOWS = False


def get_aws_tags():
    if os.environ.get('AWS_TEST_TAGS'):
        return os.environ.get('AWS_TEST_TAGS')
    elif os.path.exists(local_config_file):
        config_data = configparser.ConfigParser()
        config_data.read(local_config_file)
        if 'pytest' in config_data:
            pytest_config = config_data['pytest']
            if pytest_config.get('tags'):
                return pytest_config.get('tags')
    else:
        return None


def make_local_dir(name: str):
    if not os.path.exists(name):
        path_dir = os.path.dirname(name)
        if not os.path.exists(path_dir):
            make_local_dir(path_dir)
        try:
            os.mkdir(name)
        except OSError:
            raise


def cmd_exec(command: Union[str, List[str]], directory: str):
    buffer = io.BytesIO()

    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=directory)

    while True:
        data = p.stdout.read()
        if not data:
            break
        buffer.write(data)

    p.communicate()

    if p.returncode != 0:
        raise ValueError("command exited with non-zero return code")

    buffer.seek(0)
    return buffer


def cli_run(cmd: str, *args: str, input_file: str = None):
    command_output = ""
    run_cmd = [
        cmd,
        *args
    ]

    p = subprocess.Popen(run_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=WINDOWS)

    if input_file:
        with open(input_file, 'rb') as input_data:
            while True:
                line = input_data.readline()
                if not line:
                    break
                p.stdin.write(line)
            p.stdin.close()

    while True:
        line = p.stdout.readline()
        if not line:
            break
        line_string = line.decode("utf-8")
        command_output += line_string

    p.wait()

    return p.returncode, command_output


def random_string(n=32):
    return ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=n))


def encrypt_file(file_name: str, key_text: str):
    with open(file_name, "rb") as in_file:
        raw = in_file.read()
        digest = sha256(raw).digest()
    in_bytes = bytearray()
    in_bytes.extend(digest)
    in_bytes.extend(raw)
    output_file = file_name + ".enc"
    iv = Random.new().read(AES.block_size)
    bs = AES.block_size
    key = hashlib.sha256(key_text.encode()).digest()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    block = in_bytes + (bs - len(in_bytes) % bs) * chr(bs - len(in_bytes) % bs).encode()
    result = base64.b64encode(iv + cipher.encrypt(block)).decode("utf-8")
    with open(output_file, "w") as out_file:
        out_file.write(result)
        out_file.write("\n")


def decrypt_file(file_name: str, key_text: str):
    with open(file_name, "r") as in_file:
        enc = in_file.read()
    data = base64.b64decode(enc)
    iv = data[:AES.block_size]
    key = hashlib.sha256(key_text.encode()).digest()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    block = cipher.decrypt(data[AES.block_size:])
    result = block[:-ord(block[len(block) - 1:])]
    digest = result[0:32]
    raw = result[32:]
    check = sha256(raw).digest()
    if check != digest:
        raise ValueError("can not decrypt: checksum mismatch: check that the key is correct")
    path = os.path.dirname(file_name)
    output_file = os.path.join(path, Path(file_name).stem)
    with open(output_file, "wb") as out_file:
        out_file.write(raw)


def create_cred_package(file_name: str):
    with tarfile.open(file_name, mode='w:gz') as tar:
        tar.add(ssh_key_path, arcname=ssh_key_relative_path)
        tar.add(ssh_pub_key_path, arcname=ssh_pub_key_relative_path)
        tar.add(capella_config_path, arcname=capella_config_relative_path, recursive=True)
        tar.add(aws_config_dir, arcname=os.path.relpath(aws_config_dir, Path.home()), recursive=True)
        tar.add(gcp_config_dir, arcname=os.path.relpath(gcp_config_dir, Path.home()), recursive=True)
        tar.add(azure_config_dir, arcname=os.path.relpath(azure_config_dir, Path.home()), recursive=True)
        tar.add(local_config_file, arcname=os.path.relpath(local_config_file, Path.home()))
