import logging
import subprocess
from pathlib import Path
from typing import Optional

KUBECTL = "/usr/bin/kubectl"


def _kubectl(*args):
    cmd = [KUBECTL]
    cmd.extend(args)
    logging.debug(f"subprocess.run {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True)


def apply(yaml: Path, namespace: Optional[str] = None) -> None:
    command = ["apply", "-f", str(yaml)]
    if namespace is not None:
        command.append(f"--namespace={namespace}")
    return _kubectl(*command).check_returncode()


def create(type: str, name: str) -> None:
    resp = _kubectl("create", type, name)
    try:
        resp.check_returncode()
    except subprocess.CalledProcessError as err:
        error = err.stderr.decode()
        logging.error(f"Error creating {type} {name}: {error}")
        raise


def delete(type: str, name: str) -> None:
    resp = _kubectl("delete", type, name)
    try:
        resp.check_returncode()
    except subprocess.CalledProcessError as err:
        error = err.stderr.decode()
        logging.error(f"Error deleting {type} {name}: {error}")
        raise
