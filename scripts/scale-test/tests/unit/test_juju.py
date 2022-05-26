from unittest.mock import patch

import pytest

from benchmarks.juju import run

JUJU_MODULE = "benchmarks.juju"


@patch(f"{JUJU_MODULE}._juju")
def test_run(_juju):
    command = "some command"

    # wrong input values
    with pytest.raises(ValueError):
        run(command)

    with pytest.raises(ValueError):
        run(command, unit="foo", app="bar")

    # a specific unit
    run(command, unit="foo")
    _juju.assert_called_once_with("run", "-u", "foo", "--", command)
    _juju.reset_mock()

    # all units
    run(command, app="myapp")
    _juju.assert_called_once_with("run", "-a", "myapp", "--", command)
