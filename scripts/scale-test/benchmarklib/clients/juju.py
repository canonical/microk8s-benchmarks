import json
import logging
import subprocess
from typing import Dict, List, Optional

JUJU = "/snap/bin/juju"
JUJU_WAIT = "/snap/bin/juju-wait"


class JujuSession:
    """
    This wrapper class represents a juju client session.
    It stores the model and app attributes in its state, allowing the caller
    to perform juju operations on different models simultaneously. For instance:

    >>> session1 = JujuSession("model1", "myapp")
    >>> session2 = JujuSession("model1", "myapp")

    >>> for session in [session1, session2]:
    ...    session.add_model()
    ...    session.deploy("ubuntu")
    """

    def __init__(self, model: str, app: str):
        self.model = model
        self.app = app

    def run_in_unit(
        self, *command, unit: str, timeout: Optional[str] = None, format=None
    ):
        return run(
            *command, unit=unit, model=self.model, timeout=timeout, format=format
        )

    def run_in_units(self, *command, units: List[str], format=None):
        return run(*command, units=units, model=self.model, format=format)

    def run_in_all_units(self, *command, timeout: Optional[str] = None):
        return run(*command, app=self.app, model=self.model, timeout=timeout)

    def add_model(self):
        return add_model(self.model)

    def destroy_model(self):
        return destroy_model(self.model)

    def status(self, format=None):
        return status(self.model, format=format)

    def wait_for_model(self):
        return wait_for_model(self.model)

    def deploy(self, charm_name: str, *extra_args):
        return deploy(charm_name, self.model, *extra_args, self.app)

    def add_units(self, units: int):
        return add_unit(units, self.app, self.model)

    def get_units(self) -> List[Dict[str, str]]:
        """
        Build the list of ubuntu units from the juju status output
        """
        units = []
        status = json.loads(self.status(format="json").stdout.decode())
        for unit_name, unit_data in status["applications"][self.app]["units"].items():
            ip = unit_data["public-address"]
            machine_id = unit_data["machine"]
            hostname = status["machines"][machine_id]["hostname"]
            units.append(dict(name=unit_name, instance_id=hostname, ip=ip))
        return units


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
    unit: Optional[str] = None,
    units: Optional[List[str]] = None,
    app: Optional[str] = None,
    timeout: Optional[str] = None,
    model: Optional[str] = None,
    format: Optional[str] = None,
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
    if model:
        juju_command.extend(["-m", model])
    if timeout:
        juju_command.extend(["--timeout", timeout])
    if format:
        juju_command.extend(["--format", format])

    if app:
        juju_command.extend(["-a", app, "--", *command])
    else:
        juju_command.extend(["-u", ",".join(units), "--", *command])
    return _juju(*juju_command)


def add_model(model_name: str):
    return _juju("add-model", model_name)


def deploy(charm_name: str, model: str, app_name: str, *extra_args):
    return _juju("deploy", charm_name, "-m", model, *extra_args, app_name)


def add_unit(units: int, app_name: str, model: str):
    return _juju("add-unit", "-m", model, "-n", str(units), app_name)


def status(model: str, format: Optional[str] = None):
    cmd = ["status", "-m", model]
    if format:
        cmd.append(f"--format={format}")
    return _juju(*cmd)


def wait_for_model(model: str):
    return _juju_wait("-m", model)


def destroy_model(model: str):
    return _juju("destroy-model", "-y", model)
