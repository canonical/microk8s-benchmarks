from unittest.mock import patch

import pytest

from benchmarklib.clients.juju import JujuSession, run

JUJU_MODULE = "benchmarklib.clients.juju"


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

    # two units
    run(command, units=["foo", "bar"])
    _juju.assert_called_once_with("run", "-u", "foo,bar", "--", command)
    _juju.reset_mock()

    # all units in an application
    run(command, app="myapp")
    _juju.assert_called_once_with("run", "-a", "myapp", "--", command)
    _juju.reset_mock()

    # with timeout
    run(command, app="myapp", timeout="10s")
    _juju.assert_called_once_with(
        "run", "--timeout", "10s", "-a", "myapp", "--", command
    )
    _juju.reset_mock()

    # with model arg
    run(command, app="myapp", model="foobar")
    _juju.assert_called_once_with("run", "-m", "foobar", "-a", "myapp", "--", command)


@patch("benchmarklib.clients.juju.status")
def test_get_units(_juju_status):
    _juju_status().stdout = b"""{"model":{"name":"microk8s","type":"iaas","controller":"mk8s-testing-controller","cloud":"mk8s-testing","region":"Boston","version":"2.9.29","model-status":{"current":"available","since":"26 May 2022 12:58:26+02:00"},"sla":"unsupported"},"machines":{"0":{"juju-status":{"current":"started","since":"26 May 2022 13:02:29+02:00","version":"2.9.29"},"hostname":"juju-c6c89a-0","dns-name":"10.246.154.108","ip-addresses":["10.246.154.108"],"instance-id":"juju-c6c89a-0","machine-status":{"current":"allocating","message":"powering on","since":"26 May 2022 12:58:46+02:00"},"modification-status":{"current":"idle","since":"26 May 2022 12:58:35+02:00"},"series":"focal","network-interfaces":{"ens192":{"ip-addresses":["10.246.154.108"],"mac-address":"00:50:56:09:5c:07","gateway":"10.246.154.1","is-up":true}},"constraints":"arch=amd64 cores=2 mem=4096M root-disk=40960M","hardware":"arch=amd64 cores=2 mem=4096M root-disk=40960M root-disk-source=vsanDatastore"},"1":{"juju-status":{"current":"started","since":"26 May 2022 13:02:29+02:00","version":"2.9.29"},"hostname":"juju-c6c89a-1","dns-name":"10.246.154.111","ip-addresses":["10.246.154.111"],"instance-id":"juju-c6c89a-1","machine-status":{"current":"allocating","message":"powering on","since":"26 May 2022 12:58:46+02:00"},"modification-status":{"current":"idle","since":"26 May 2022 12:58:35+02:00"},"series":"focal","network-interfaces":{"ens192":{"ip-addresses":["10.246.154.111"],"mac-address":"00:50:56:09:5c:07","gateway":"10.246.154.1","is-up":true}},"constraints":"arch=amd64 cores=2 mem=4096M root-disk=40960M","hardware":"arch=amd64 cores=2 mem=4096M root-disk=40960M root-disk-source=vsanDatastore"}},"applications":{"microk8s-node":{"charm":"ubuntu","series":"focal","os":"ubuntu","charm-origin":"charmhub","charm-name":"ubuntu","charm-rev":19,"charm-channel":"stable","exposed":false,"application-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"units":{"microk8s-node/0":{"workload-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"juju-status":{"current":"idle","since":"26 May 2022 13:02:32+02:00","version":"2.9.29"},"leader":true,"machine":"0","public-address":"10.246.154.108"},"microk8s-node/1":{"workload-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"juju-status":{"current":"idle","since":"26 May 2022 13:02:32+02:00","version":"2.9.29"},"leader":false,"machine":"1","public-address":"10.246.154.111"}},"version":"20.04"}},"storage":{},"controller":{"timestamp":"13:03:13+02:00"}}"""  # noqa
    expected_units = [
        dict(name="microk8s-node/0", ip="10.246.154.108", instance_id="juju-c6c89a-0"),
        dict(name="microk8s-node/1", ip="10.246.154.111", instance_id="juju-c6c89a-1"),
    ]
    juju = JujuSession(model="foo", app="microk8s-node")
    assert juju.get_units() == expected_units
