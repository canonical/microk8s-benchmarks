from unittest.mock import Mock, patch

import pytest

from benchmarks.experiment import Experiment


@patch("benchmarks.experiment.Experiment.teardown")
def test_run_calls_teardown_on_graceful_exit(_teardown):
    exp = Experiment("foo", None)

    exp.run()

    _teardown.assert_called_once()


@patch("benchmarks.experiment.Experiment.teardown")
@patch("benchmarks.experiment.Experiment.start")
def test_run_calls_teardown_on_exception(_start, _teardown):
    exp = Experiment("foo", None)

    # Unhandled exception
    _start.side_effect = Exception()
    with pytest.raises(Exception):
        exp.run()

    _teardown.assert_called_once()

    # Keyboard interrupt
    _start.side_effect = KeyboardInterrupt()
    _teardown.reset_mock()

    exp.run()

    _teardown.assert_called_once()


def test_cluster_is_reset_between_workloads():
    cluster = Mock()
    exp = Experiment("foo", cluster)
    exp.register_workloads([Mock(), Mock()])

    exp.start()

    assert cluster.create_namespace.call_count == 2
    assert cluster.delete_namespace.call_count == 2


def test_tmp_namespace():
    cluster = Mock()
    exp = Experiment("foo", cluster)

    with exp.tmp_namespace() as namespace:
        assert namespace == "foo"
        cluster.create_namespace.assert_called_once_with("foo")
        cluster.delete_namespace.assert_not_called()

    cluster.delete_namespace.assert_called_once_with("foo")


def test_workloads_are_applied_in_namespace():
    cluster = Mock()
    workload = Mock()
    exp = Experiment("foo", cluster)
    exp.run_workload(workload)

    workload.apply.assert_called_once_with(namespace="foo")
