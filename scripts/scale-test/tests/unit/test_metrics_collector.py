import random
from pathlib import Path

import pytest

from benchmarklib.metrics.base import ConstantField, Metric, VariableField
from benchmarklib.metrics.collector import MetricsCollector


class MyTestMetric(Metric):
    def __init__(self, name="test"):
        super().__init__(name)
        self.add_field(ConstantField("cluster_size", 10))
        self.add_field(VariableField("memory_usage", self.get_value))

    def get_value(self):
        return int(random.uniform(0, 10))


def test_context_manager(temp_dir):
    metric = MyTestMetric("foo")

    store_path = Path(temp_dir)
    collector = MetricsCollector(
        metrics=[],
        store_at=store_path,
        poll_period=0.01,
    )

    # It should start only if there are metrics to record
    with collector:
        assert collector._started is False
        assert collector.thread is None

    # Check that it started
    collector.metrics = [metric]
    with collector:
        assert collector.thread
        assert collector._started is True

    assert collector._started is False

    with open(store_path / "metric-foo.csv", "r") as f:
        contents = f.read()
        lines = contents.split()
        assert len(lines) > 1
        assert lines[0] == "cluster_size,memory_usage"
        assert len(lines[1].split(",")) == 2


def test_context_manager_dumps_metrics_on_exception(temp_dir):
    metric = MyTestMetric("foo")

    store_path = Path(temp_dir)
    collector = MetricsCollector(
        metrics=[metric],
        store_at=store_path,
        poll_period=0.01,
    )

    with pytest.raises(KeyboardInterrupt):
        with collector:
            assert collector.thread
            assert collector._started is True
            raise KeyboardInterrupt()

    assert collector._started is False

    # Check that dump was called on metrics too
    with open(store_path / "metric-foo.csv", "r") as f:
        contents = f.read()
        lines = contents.split()
        assert len(lines) >= 1
        assert lines[0] == "cluster_size,memory_usage"


def test_exception_in_thread_is_handled():
    class FailingMetric(Metric):
        def __init__(self):
            super().__init__("I will fail")
            self.add_field(VariableField("fail", self.get_value))

        def get_value(self):
            raise KeyError("some error")

    metric = FailingMetric()
    collector = MetricsCollector(
        metrics=[metric],
        poll_period=0,
    )
    with pytest.raises(KeyError):
        with collector:
            pass


def _test_collect_parallel_vs_serially():
    import time

    from benchmarklib.utils import pp_time

    class MyMetric(Metric):
        def __init__(self, name):
            super().__init__(name)
            self.add_field(ConstantField("cluster_size", 10))
            self.add_field(VariableField("memory_usage", self.get_value))

        def get_value(self):
            sleep_time = random.uniform(0, 3)
            print(f"Going to sleep for {sleep_time}s")
            time.sleep(sleep_time)
            return sleep_time

    metrics = [MyMetric(f"foo_{i}") for i in range(10)]
    collector = MetricsCollector(metrics=metrics, poll_period=0)

    start = time.time()
    collector._collect_serially()
    duration = time.time() - start
    print(f"Serial Took = {pp_time(duration)}")

    start = time.time()
    collector._collect_in_parallel()
    duration = time.time() - start
    print(f"Serial Took = {pp_time(duration)}")
