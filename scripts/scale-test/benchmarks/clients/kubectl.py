import logging
import subprocess
from pathlib import Path
from typing import Optional

KUBECTL = "/usr/bin/kubectl"


def _kubectl(*args):
    cmd = [KUBECTL]
    cmd.extend(args)
    logging.debug(f"subprocess.run {';'.join(cmd)}")
    return subprocess.run(cmd, capture_output=True)


def apply(yaml: Path, namespace: Optional[str] = None) -> None:
    command = ["apply", "-f", yaml]
    if namespace is not None:
        command.append(f"--namespace={namespace}")
    return _kubectl(*command).check_returncode()


def create(type: str, name: str):
    return _kubectl("create", type, name)


def delete(type: str, name: str):
    return _kubectl("delete", type, name)