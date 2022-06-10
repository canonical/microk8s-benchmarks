import logging
import subprocess
from typing import List, Optional

from benchmarklib.models import Unit

JUJU = "/snap/bin/juju"
JUJU_WAIT = "/snap/bin/juju-wait"


def _juju(*args):
    cmd = [JUJU]
    cmd.extend(args)
    logging.debug(f"subprocess.run {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True)


def _juju_wait(*args):
    cmd = [JUJU_WAIT]
    cmd.extend(args)
    logging.debug(f"subprocess.run {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True)


def run(
    *command,
    unit: Optional[Unit] = None,
    units: Optional[List[Unit]] = None,
    app: Optional[str] = None,
    timeout: str = None,
):
    """
    Run a command on a juju unit or on all units of a particular application
    """
    args = [unit, units, app]
    if len([arg for arg in args if arg]) != 1:
        raise ValueError("Need to specify either units, unit or an app")

    if unit:
        units = [unit]

    juju_command = ["run"]
    if timeout:
        juju_command.extend(["--timeout", timeout])
    if app:
        juju_command.extend(["-a", app, "--", *command])
    else:
        juju_command.extend(["-u", ",".join(units), "--", *command])
    return _juju(*juju_command)


def add_model(model_name: str):
    return _juju("add-model", model_name)


def deploy(charm_name: str, *extra_args):
    return _juju("deploy", charm_name, *extra_args)


def add_unit(units: int, application_name: str):
    return _juju("add-unit", "-n", str(units), application_name)


def status(format: str = None):
    cmd = ["status"]
    if format:
        cmd.append(f"--format={format}")
    return _juju(*cmd)


def wait_for_model(model: str):
    return _juju_wait("-m", model)


def destroy_model(model: str):
    return _juju("destroy-model", "-y", model)