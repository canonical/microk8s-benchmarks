import random
from ast import Param
from audioop import mul
from pathlib import Path
from unittest.mock import Mock

from benchmarklib.metrics.base import (
    ConstantField,
    Metric,
    ParametrizedField,
    VariableField,
)


class MyTestMetric(Metric):
    def __init__(self, name="test"):
        super().__init__(name)
        self.add_field(ConstantField("cluster_size", 10))
        self.add_field(VariableField("memory_usage", self.get_value))

    def get_value(self):
        return int(random.uniform(0, 10))


class MetricWithParametrized(Metric):
    def __init__(self, name="test"):
        super().__init__(name)
        self.add_field(ConstantField("foo", 10))
        self.add_field(
            ParametrizedField(
                "cpu", param_name="param", params=[50, 30], callable=self.divide_by_10
            )
        )
        self.add_field(ConstantField("bar", 20))

    def divide_by_10(self, param):
        return param / 10


def test_sample():
    metric = MyTestMetric("foo")
    assert metric.name == "foo"
    assert metric.field_names == ["cluster_size", "memory_usage"]
    assert len(metric.samples) == 0
    metric.sample()
    metric.sample()
    assert len(metric.samples) == 2


def test_dump(temp_dir):
    path = Path(temp_dir)
    metric = MyTestMetric(name="foo")
    metric.sample()

    metric.dump(path)

    with open(path / "metric-foo.csv", "r") as f:
        contents = f.read()
        lines = contents.split()
        assert len(lines) == 2
        assert lines[0] == "cluster_size,memory_usage"
        assert len(lines[1].split(",")) == 2


def test_dump_appends(temp_dir):
    path = Path(temp_dir)

    metric = MyTestMetric(name="test_appends")
    metric.sample()
    metric.dump(path)

    other_instance = MyTestMetric(name="test_appends")
    other_instance.sample()
    other_instance.dump(path)

    with open(path / "metric-test_appends.csv", "r") as f:
        contents = f.read()
        lines = contents.split()
        assert len(lines) == 3


def test_metric_with_multiple_parametrized():
    metric = MetricWithParametrized(name="parametrized")
    metric.add_field(
        ParametrizedField(
            "other",
            param_name="param2",
            params=[100, 200],
            callable=lambda x: int(x / 10),
        )
    )

    assert metric.field_names == ["foo", "param", "cpu", "bar", "param2", "other"]
    metric.sample()

    assert metric.samples == [
        [10, 50, 5.0, 20, 100, 10],
        [10, 50, 5.0, 20, 200, 20],
        [10, 30, 3.0, 20, 100, 10],
        [10, 30, 3.0, 20, 200, 20],
    ]


def test_dump_with_parametrized_field(temp_dir):
    metric = MetricWithParametrized(name="parametrized")
    metric.sample()
    assert metric.samples == [[10, 50, 5.0, 20], [10, 30, 3.0, 20]]
    assert metric.field_names == ["foo", "param", "cpu", "bar"]

    path = Path(temp_dir)
    metric.dump(path)

    with open(path / "metric-parametrized.csv", "r") as f:
        contents = f.read()
        lines = contents.split()
        assert len(lines) == 3
        assert lines[0] == "foo,param,cpu,bar"
        assert len(lines[1].split(",")) == 4


def test_constant_field():
    value = Mock()
    field = ConstantField("foo", value)
    assert field.collect() is value


def test_variable_field():
    callable = Mock()
    field = VariableField("foo", callable)
    value = field.collect()
    callable.assert_called_once()
    assert value == callable.return_value


def test_parametrized_field():
    multiply_by_2 = lambda x: x * 2
    field = ParametrizedField(
        "foo", param_name="myparam", params=[1, 2, 3], callable=multiply_by_2
    )

    # Check that generator yields the right tuples
    values = [v for v in field.collect()]
    assert values == [(1, 2), (2, 4), (3, 6)]
