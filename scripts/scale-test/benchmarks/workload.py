import logging
import time
from pathlib import Path

from benchmarks.utils import pp_time

from .clients import kubectl


class Workload:
    def __init__(self, yaml: Path, duration: int, poll_period: int = 5):
        self.yaml = yaml
        self.duration = duration
        self.poll_period = poll_period

    def __str__(self) -> str:
        return f"Workload[{self.yaml}]"

    def apply(self) -> None:
        kubectl.apply(self.yaml)

    def wait(self) -> None:
        start = time.time()
        while True:
            remaining = int(self.duration - (time.time() - start))
            if remaining <= 0:
                break
            logging.info(f"Waiting for {self}... {pp_time(remaining)} left")
            time.sleep(self.poll_period)
