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

    cluster.reset.assert_called_once()
