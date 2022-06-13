import logging
import time
from pathlib import Path
from typing import Optional

from benchmarklib.utils import pp_time

from .clients import kubectl


class Workload:
    def __init__(
        self,
        yaml: Path,
        duration: int,
        name: Optional[str] = None,
        poll_period: int = 30,
    ):
        self.yaml = yaml
        self._name = name
        self.duration = duration
        self.poll_period = poll_period

    @property
    def name(self):
        if self._name is None:
            # Infer from yaml name
            self._name = self.yaml.name
        return self._name

    def __str__(self) -> str:
        return f"Workload[{self.name}]"

    def apply(self, namespace: Optional[str] = None) -> None:
        kubectl.apply(self.yaml, namespace=namespace)

    def wait(self) -> None:
        # TODO: move this logic to benchmarklib/experiment.py
        # this doesn't belong here...
        start = time.time()
        while True:
            remaining = int(self.duration - (time.time() - start))
            if remaining <= 0:
                break
            logging.info(f"Waiting for {self}... {pp_time(remaining)} left")
            time.sleep(self.poll_period)
