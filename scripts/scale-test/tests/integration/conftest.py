import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from benchmarklib.clients.juju import JujuSession
from benchmarklib.metrics import collector
from benchmarklib.models import ClusterInfo, Unit
from scale_test import experiment


def test_juju_status_output():
    return {
        "machines": {
            "0": {"hostname": "juju-c6c89a-0"},
            "1": {"hostname": "juju-c6c89a-1"},
        },
        "applications": {
            "registry": {
                "units": {
                    "registry/0": {"machine": "0", "public-address": "10.246.154.108"}
                }
            },
            "microk8s-node": {
                "units": {
                    "microk8s-node/0": {
                        "machine": "0",
                        "public-address": "10.246.154.108",
                    },
                    "microk8s-node/1": {
                        "machine": "1",
                        "public-address": "10.246.154.111",
                    },
                }
            },
        },
    }


@pytest.fixture()
def juju_status_mock():
    with patch.object(JujuSession, "status") as _status:
        _status().stdout = json.dumps(test_juju_status_output()).encode()
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
def pods_ready_mock():
    with patch("benchmarklib.cluster.Microk8sCluster.pods_ready", return_value=True):
        yield


@pytest.fixture()
def run_in_master_node_mock():
    metrics = """apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.05"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.1"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.45"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="60"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="+Inf"} 6
apiserver_request_duration_seconds_sum{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version=""} 0.001088356
apiserver_request_duration_seconds_count{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version=""} 6
"""  # noqa

    return_value = Mock(stdout=metrics.encode())
    with patch(
        "scale_test.metrics.Microk8sCluster.run_in_master_node",
        return_value=return_value,
    ):
        yield


@pytest.fixture()
def setup_cluster_fixtures(
    juju_status_mock, subprocess_run_mock, all_nodes_joined_mock, path_cwd_mock
):
    yield


@pytest.fixture()
def docker_images_json():
    f = tempfile.NamedTemporaryFile(delete=False)
    images = {"foo": "docker.io/foo:2.1.1", "bar": "epa.pi/bar:0.0.1"}
    f.write(json.dumps(images).encode())
    f.file.flush()

    yield f.name

    f.close()


@pytest.fixture()
def setup_registry_fixtures(
    setup_cluster_fixtures,
    docker_images_json,
):
    yield


@pytest.fixture()
def experiment_fixtures(
    run_in_master_node_mock,
    subprocess_run_mock,
    workload_time,
    cluster_json,
    fetch_kubeconfig,
    data_lake,
    temp_dir,
    collector_poll_period,
    pods_ready_mock,
):
    yield


@pytest.fixture()
def benchmark_fixtures(
    experiment_fixtures,
    setup_cluster_fixtures,
):
    yield
