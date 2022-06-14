import abc
import csv
import itertools
from pathlib import Path
from typing import Any, List

Sample = List[Any]


class Field(metaclass=abc.ABCMeta):
    def collect(self):
        raise NotImplementedError()


class ConstantField(Field):
    """
    Useful for dimensions that are constants during the experiment time,
    such as the number of nodes in the current cluster.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def collect(self):
        return self.value


class VariableField(Field):
    """
    Use to measure a particular metric that change over the experiment
    time, such as memory or cpu usage of a specific process.
    """

    def __init__(self, name, callable):
        self.name = name
        self.callable = callable

    def collect(self):
        return self.callable()


class NodeAwareField(Field):
    """
    Use to measure metrics that change over time across various nodes.
    It will normalizes the resulting metric by node name
    """

    def __init__(self, name, nodes, callable):
        self.name = name
        self.nodes = nodes
        self.callable = callable

    def collect(self):
        for node in self.nodes:
            yield node.name, self.callable(node)


class Metric:
    """
    A metric represent a set of samples measured. Each sample is
    formed of a list of fields with the corresponding sampled values.

    All samples of a metric can be dumped on a csv file.

    Each field correspond to csv columns: the field name matches
    the column header, and the raws of that column are the collected values.
    """

    def __init__(self, name: str):
        self.name = name
        self.fields: List[Field] = []
        self.samples: List[Sample] = []

    def add_field(self, field: Field):
        self.check_can_add_field(field)
        self.fields.append(field)

    def check_can_add_field(self, field):
        if not isinstance(field, NodeAwareField):
            return

        # Check if there is already a NodeAwareField added
        if any([isinstance(f, NodeAwareField) for f in self.fields]):
            raise ValueError("Multiple NodeAwareField fields is not supported")

    def collect_fields(self) -> List[Sample]:
        def _insert_value(value, samples):
            if samples == []:
                samples.append([value])
            else:
                for sample in samples:
                    sample.append(value)

        samples = []

        for field in self.fields:
            if isinstance(field, NodeAwareField):
                node_values = [[node, value] for node, value in field.collect()]
                product = itertools.product(samples, node_values)
                samples = [prev + new for prev, new in product]
            else:
                # Collect new field value and append
                # it to the existing list of samples
                value = field.collect()
                _insert_value(value, samples)

        return samples

    def clear(self):
        self.samples = []

    @property
    def field_names(self) -> List[str]:
        names = []
        for field in self.fields:
            if isinstance(field, NodeAwareField):
                names.append("node")
                names.append(field.name)
            else:
                names.append(field.name)
        return names

    def remove_field(self, field: Field) -> None:
        self.fields.remove(field)

    def sample(self):
        sampled_values = self.collect_fields()
        self.samples.extend(sampled_values)

    def dump(self, path: Path) -> None:
        metric_file = path / f"metric-{self.name}.csv"
        csv_already_exists = metric_file.exists()
        with open(metric_file, "a") as csv_file:
            csvwriter = csv.writer(csv_file)
            if not csv_already_exists:
                # Write row only the first time
                csvwriter.writerow(self.field_names)
            csvwriter.writerows(self.samples)

    def __str__(self) -> str:
        return f"Metric[{self.name}]"
