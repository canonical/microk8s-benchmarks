import logging
import subprocess
from pathlib import Path

KUBECTL = "/usr/bin/kubectl"


def _kubectl(*args):
    cmd = [KUBECTL]
    cmd.extend(args)
    logging.debug(f"subprocess.run {';'.join(cmd)}")
    return subprocess.run(cmd, capture_output=True)


def apply(yaml: Path) -> None:
    _kubectl("apply", "-f", yaml).check_returncode()
