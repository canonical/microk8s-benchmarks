import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scale_test import experiment


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
def scale_test_mocks(
    subprocess_run_mock,
    workload_time,
    cluster_json,
    fetch_kubeconfig,
    data_lake,
    temp_dir,
):
    yield


def test_main(scale_test_mocks, cluster_json):
    with patch.object(sys, "argv", ["scale_testing", "-c", cluster_json]):

        experiment.main()
