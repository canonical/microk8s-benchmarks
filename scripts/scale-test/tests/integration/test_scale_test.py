import sys
from unittest.mock import patch

import pytest

import scale_test


@pytest.fixture()
def workload_time():
    with patch.object(scale_test, "WORKLOAD_TIME", new=1):
        yield


@pytest.fixture()
def fetch_kubeconfig():
    with patch(
        "benchmarks.experiment.Microk8sCluster.fetch_kubeconfig", return_value="foobar"
    ) as _fetch:
        yield _fetch


def test_main(subprocess_run_mock, workload_time, cluster_json, fetch_kubeconfig):
    with patch.object(sys, "argv", ["scale_testing", "-c", cluster_json]):
        scale_test.main()
