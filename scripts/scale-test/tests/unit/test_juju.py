from unittest.mock import patch

import pytest

from benchmarks.clients.juju import run

JUJU_MODULE = "benchmarks.clients.juju"


@patch(f"{JUJU_MODULE}._juju")
def test_run(_juju):
    command = "some command"

    # wrong input values
    with pytest.raises(ValueError):
        run(command)

    with pytest.raises(ValueError):
        run(command, unit="foo", app="bar")

    with pytest.raises(ValueError):
        run(command, units=["foo"], app="bar")

    with pytest.raises(ValueError):
        run(command, units=["foo"], unit="bar")

    # a specific unit
    run(command, unit="foo")
    _juju.assert_called_once_with("run", "-u", "foo", "--", command)
    _juju.reset_mock()

    # a few units
    run(command, units=["foo", "bar"])
    _juju.assert_called_once_with("run", "-u", "foo", "bar", "--", command)
    _juju.reset_mock()

    # all units
    run(command, app="myapp")
    _juju.assert_called_once_with("run", "-a", "myapp", "--", command)
    _juju.reset_mock()

    # with timeout
    run(command, app="myapp", timeout="10s")
    _juju.assert_called_once_with(
        "run", "--timeout", "10s", "-a", "myapp", "--", command
    )
