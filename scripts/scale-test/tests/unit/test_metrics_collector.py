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
