from unittest.mock import Mock, patch

import pytest

from benchmarks.benchmark import Benchmark


@patch("benchmarks.benchmark.Benchmark.teardown")
def test_run_calls_teardown_on_graceful_exit(_teardown):
    bmk = Benchmark("foo", None)

    bmk.run()

    _teardown.assert_called_once()


@patch("benchmarks.benchmark.Benchmark.teardown")
@patch("benchmarks.benchmark.Benchmark.start")
def test_run_calls_teardown_on_exception(_start, _teardown):
    bmk = Benchmark("foo", None)

    # Unhandled exception
    _start.side_effect = Exception()
    with pytest.raises(Exception):
        bmk.run()

    _teardown.assert_called_once()

    # Keyboard interrupt
    _start.side_effect = KeyboardInterrupt()
    _teardown.reset_mock()

    bmk.run()

    _teardown.assert_called_once()


def test_cluster_is_reset_between_workloads():
    cluster = Mock()
    bmk = Benchmark("foo", cluster)
    bmk.register_workloads([Mock(), Mock()])

    bmk.start()

    assert cluster.create_namespace.call_count == 2
    assert cluster.delete_namespace.call_count == 2


def test_tmp_namespace():
    cluster = Mock()
    bmk = Benchmark("foo", cluster)

    with bmk.tmp_namespace() as namespace:
        assert namespace == "foo"
        cluster.create_namespace.assert_called_once_with("foo")
        cluster.delete_namespace.assert_not_called()

    cluster.delete_namespace.assert_called_once_with("foo")


def test_workloads_are_applied_in_namespace():
    cluster = Mock()
    workload = Mock()
    bmk = Benchmark("foo", cluster)
    bmk.run_workload(workload)

    workload.apply.assert_called_once_with(namespace="foo")
