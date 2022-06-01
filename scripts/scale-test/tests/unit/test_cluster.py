import json
import logging
from subprocess import CalledProcessError
from unittest.mock import mock_open, patch

import pytest

from benchmarks.clients import juju
from benchmarks.cluster import Microk8sCluster
from benchmarks.models import ClusterInfo, Unit

TEST_UNIT = Unit(name="foo", ip="bar", instance_id="ba")

TEST_CLUSTER_INFO = ClusterInfo(master=TEST_UNIT, control_plane=[TEST_UNIT], workers=[])


def test_from_file():
    read_data = json.dumps(TEST_CLUSTER_INFO.to_dict()).encode()

    with patch("benchmarks.cluster.open", mock_open(read_data=read_data)):

        cluster = Microk8sCluster.from_file("/some/path")

        assert isinstance(cluster, Microk8sCluster)
        assert cluster.info == TEST_CLUSTER_INFO


def test_run_in_unit_logs_process_error(caplog):
    with patch.object(juju, "run") as _juju_run:
        error = CalledProcessError(2, "foo")
        _juju_run.return_value.check_returncode.side_effect = error
        cluster = Microk8sCluster(info=TEST_CLUSTER_INFO)

        with pytest.raises(CalledProcessError):

            cluster.run_in_unit(cluster.info.master, "blah")

        assert caplog.records[0].levelno == logging.ERROR
        assert "Error running blah on foo" in caplog.records[0].message
