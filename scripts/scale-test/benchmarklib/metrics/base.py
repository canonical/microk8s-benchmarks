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


class ParametrizedField(Field):
    """
    To be used for measurements that need a parameter.

    For instance, when measuring memory consumption of a set of nodes,
    it will normalize the node parameter as a column of the CSV file

    >>> def get_memory_usage(node):
    >>>    ...

    >>> nodes = ["node1", "node2"]
    >>> field = ParametrizedField("memory", param_name="node", params=nodes, callable=get_memory_usage)
    >>> m = Metric("mymetric")
    >>> m.add_field(field)
    >>> m.sample()
    >>> m.field_names
    ["node", "memory"]
    >>> m.samples
    [["node1", 10], ["node2", 11]]
    """

    def __init__(self, name, param_name, params, callable):
        self.name = name
        self.param_name = param_name
        self.params = params
        self.callable = callable

    def collect(self):
        for param in self.params:
            yield param, self.callable(param)


class Metric:
    """
    This class allows to perform measurements during the execution of a workload.
    All samples of a metric can be dumped on a csv file.

    Each added field corresponds to a csv column: the field name matches
    the column header, and the raws of that column are the collected values for
    that field.

    It is to be used directly:

    >>> m = Metric(name="mymetric")
    >>> m.add_field(VariableField("cpu", callable=get_cpu_usage))
    >>> m.sample()

    or by subclassing it:

    class MyMetric(Metric):
        def __init__(self):
            super().__init__(name="mymetric")
            self.add_field(VariableField("cpu", callable=get_cpu_usage))

    >>> m = MyMetric()
    >>> m.sample()

    # This will create a metric-mymetric.csv file under ~/my/data/folder
    >>> m.dump("~/my/data/folder")
    """

    def __init__(self, name: str):
        self.name = name
        self.fields: List[Field] = []
        self.samples: List[Sample] = []

    def add_field(self, field: Field):
        self.fields.append(field)

    def collect_fields(self) -> List[Sample]:
        samples = []
        for field in self.fields:
            if isinstance(field, ParametrizedField):
                # Collect all values for each param, and
                # extend the existing samples with them.
                param_values = [[param, value] for param, value in field.collect()]
                product = itertools.product(samples, param_values)
                samples = [prev + new for prev, new in product]
            else:
                # Collect new field value and append
                # it to the existing list of samples
                value = field.collect()
                if samples == []:
                    samples.append([value])
                else:
                    for sample in samples:
                        sample.append(value)
        return samples

    def clear(self):
        self.samples = []

    @property
    def field_names(self) -> List[str]:
        names = []
        for field in self.fields:
            if isinstance(field, ParametrizedField):
                names.append(field.param_name)
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
        """
        Store the collected metrics into a csv file
        """
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
