import json
import logging
from subprocess import CalledProcessError
from unittest.mock import mock_open, patch

import pytest
from utils import get_cluster_info

from benchmarklib.clients import juju
from benchmarklib.cluster import ClusterCommandError, Microk8sCluster

TEST_CLUSTER_INFO = get_cluster_info()


def test_from_file():
    read_data = json.dumps(TEST_CLUSTER_INFO.to_dict()).encode()

    with patch("benchmarklib.cluster.open", mock_open(read_data=read_data)):

        cluster = Microk8sCluster.from_file("/some/path")

        assert isinstance(cluster, Microk8sCluster)
        assert cluster.info == TEST_CLUSTER_INFO


def test_run_in_unit_logs_process_error(caplog):
    with patch.object(juju, "run") as _juju_run:
        error = CalledProcessError(2, "foo")
        _juju_run.return_value.check_returncode.side_effect = error
        cluster = Microk8sCluster(info=TEST_CLUSTER_INFO)

        with pytest.raises(ClusterCommandError) as exc:
            cluster.run_in_unit(cluster.info.master, "blah")

        assert exc.value.command == "blah"
        assert exc.value.stdout
        assert exc.value.stderr

        assert caplog.records[0].levelno == logging.ERROR
        assert "Error running blah on" in caplog.records[0].message
