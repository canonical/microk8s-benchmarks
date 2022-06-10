import abc
import csv
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
    To use when measuring values that change over the experiment
    time, such as memory or cpu usage of a specific process.
    """

    def __init__(self, name, callable):
        self.name = name
        self.callable = callable

    def collect(self):
        return self.callable()


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
        self.fields.append(field)

    def collect_field_values(self) -> Sample:
        sample = []
        for field in self.fields:
            sample.append(field.collect())
        return sample

    def clear(self):
        self.samples = []

    @property
    def field_names(self) -> List[str]:
        return [field.name for field in self.fields]

    def remove_field(self, field: Field) -> None:
        self.fields.remove(field)

    def sample(self):
        sampled_values = self.collect_field_values()
        self.samples.append(sampled_values)

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
