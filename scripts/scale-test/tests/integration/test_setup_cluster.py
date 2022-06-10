import sys
from unittest.mock import patch

import pytest

import setup_cluster


@pytest.fixture()
def all_nodes_joined_mock():
    with patch("setup_cluster.all_nodes_joined", return_value=True):
        yield


@pytest.fixture()
def setup_cluster_mocks(juju_status_mock, subprocess_run_mock, all_nodes_joined_mock):
    yield


@patch.object(sys, "argv", ["setup_cluster", "--http-proxy", "http://myproxy"])
def test_main(setup_cluster_mocks):
    setup_cluster.main()
