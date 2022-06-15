import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmarklib.clients.juju import JujuSession
from benchmarklib.metrics import collector
from benchmarklib.models import ClusterInfo, Unit
from scale_test import experiment

TEST_JUJU_STATUS_OUTPUT = b"""{"model":{"name":"microk8s","type":"iaas","controller":"mk8s-testing-controller","cloud":"mk8s-testing","region":"Boston","version":"2.9.29","model-status":{"current":"available","since":"26 May 2022 12:58:26+02:00"},"sla":"unsupported"},"machines":{"0":{"juju-status":{"current":"started","since":"26 May 2022 13:02:29+02:00","version":"2.9.29"},"hostname":"juju-c6c89a-0","dns-name":"10.246.154.108","ip-addresses":["10.246.154.108"],"instance-id":"juju-c6c89a-0","machine-status":{"current":"allocating","message":"powering on","since":"26 May 2022 12:58:46+02:00"},"modification-status":{"current":"idle","since":"26 May 2022 12:58:35+02:00"},"series":"focal","network-interfaces":{"ens192":{"ip-addresses":["10.246.154.108"],"mac-address":"00:50:56:09:5c:07","gateway":"10.246.154.1","is-up":true}},"constraints":"arch=amd64 cores=2 mem=4096M root-disk=40960M","hardware":"arch=amd64 cores=2 mem=4096M root-disk=40960M root-disk-source=vsanDatastore"},"1":{"juju-status":{"current":"started","since":"26 May 2022 13:02:29+02:00","version":"2.9.29"},"hostname":"juju-c6c89a-1","dns-name":"10.246.154.111","ip-addresses":["10.246.154.111"],"instance-id":"juju-c6c89a-1","machine-status":{"current":"allocating","message":"powering on","since":"26 May 2022 12:58:46+02:00"},"modification-status":{"current":"idle","since":"26 May 2022 12:58:35+02:00"},"series":"focal","network-interfaces":{"ens192":{"ip-addresses":["10.246.154.111"],"mac-address":"00:50:56:09:5c:07","gateway":"10.246.154.1","is-up":true}},"constraints":"arch=amd64 cores=2 mem=4096M root-disk=40960M","hardware":"arch=amd64 cores=2 mem=4096M root-disk=40960M root-disk-source=vsanDatastore"}},"applications":{"microk8s-node":{"charm":"ubuntu","series":"focal","os":"ubuntu","charm-origin":"charmhub","charm-name":"ubuntu","charm-rev":19,"charm-channel":"stable","exposed":false,"application-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"units":{"microk8s-node/0":{"workload-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"juju-status":{"current":"idle","since":"26 May 2022 13:02:32+02:00","version":"2.9.29"},"leader":true,"machine":"0","public-address":"10.246.154.108"},"microk8s-node/1":{"workload-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"juju-status":{"current":"idle","since":"26 May 2022 13:02:32+02:00","version":"2.9.29"},"leader":false,"machine":"1","public-address":"10.246.154.111"}},"version":"20.04"}},"storage":{},"controller":{"timestamp":"13:03:13+02:00"}}"""  # noqa


@pytest.fixture()
def juju_status_mock():
    with patch.object(JujuSession, "status") as _status:
        _status().stdout = TEST_JUJU_STATUS_OUTPUT
        yield _status


@pytest.fixture()
def subprocess_run_mock():
    with patch.object(subprocess, "run") as _run:
        yield _run


@pytest.fixture()
def cluster_json():
    f = tempfile.NamedTemporaryFile(delete=False)
    master = Unit(name="name", ip="ip", instance_id="id")
    cluster = ClusterInfo(
        app="app", model="foo", master=master, control_plane=[master], workers=[]
    )
    f.write(json.dumps(cluster.to_dict()).encode())
    f.file.flush()

    yield f.name

    f.close()


@pytest.fixture()
def collector_poll_period():
    with patch.object(collector, "DEFAULT_POLL_PERIOD", new=0):
        yield


@pytest.fixture()
def workload_time():
    with patch.object(experiment, "WORKLOAD_TIME", new=1):
        yield


@pytest.fixture()
def fetch_kubeconfig():
    with patch(
        "benchmarklib.experiment.Microk8sCluster.fetch_kubeconfig",
        return_value="foobar",
    ) as _fetch:
        yield _fetch


@pytest.fixture()
def data_lake(temp_dir):
    with patch(
        "benchmarklib.experiment.DATA_LAKE_PATH",
        new=Path(temp_dir),
    ):
        yield temp_dir


@pytest.fixture()
def all_nodes_joined_mock():
    with patch("setup_cluster.JujuClusterSetup.all_nodes_joined", return_value=True):
        yield


@pytest.fixture()
def setup_cluster_fixtures(
    juju_status_mock, subprocess_run_mock, all_nodes_joined_mock, path_cwd_mock
):
    yield


@pytest.fixture()
def experiment_fixtures(
    subprocess_run_mock,
    workload_time,
    cluster_json,
    fetch_kubeconfig,
    data_lake,
    temp_dir,
    collector_poll_period,
):
    yield


@pytest.fixture()
def benchmark_fixtures(
    experiment_fixtures,
    setup_cluster_fixtures,
):
    yield
