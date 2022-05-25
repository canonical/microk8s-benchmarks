import logging
import subprocess

JUJU = "/snap/bin/juju"
JUJU_WAIT = "/snap/bin/juju-wait"


def _juju(*args):
    cmd = [JUJU]
    cmd.extend(args)
    logging.debug(f"subprocess.run {cmd}")
    return subprocess.run(cmd, capture_output=True)


def _juju_wait(*args):
    cmd = [JUJU_WAIT]
    cmd.extend(args)
    logging.debug(f"subprocess.run {cmd}")
    return subprocess.run(cmd, capture_output=True)


def run(*command, unit=None, all=False):
    if unit is None and all is False:
        raise ValueError("Need to either specify a unit or all=True")
    if unit is not None and all is True:
        raise ValueError("Can't specify unit and all=True")

    if all is True:
        return _juju("run", "-a", "--", *command)
    else:
        return _juju("run", "-u", unit, "--", *command)


def add_model(model_name: str):
    return _juju("add-model", model_name)


def deploy(charm_name: str, *extra_args):
    return _juju("deploy", charm_name, *extra_args)


def add_unit(units: int, application_name):
    return _juju("add-unit", "-n", str(units), application_name)


def status():
    return _juju("status")


def wait_for_model(model):
    return _juju_wait("-m", model)


def destroy_model(model: str):
    return _juju("destroy-model", "-y", model)
