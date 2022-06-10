import logging
import threading
import time
from pathlib import Path
from typing import List

from benchmarklib.metrics.base import Metric
from benchmarklib.utils import pp_time


class MetricsCollector:
    """
    Handles the collection of a set of metrics in a separate thread
    """

    def __init__(
        self,
        metrics: List[Metric],
        store_at: Path,
        poll_period: int = 10,
    ):
        self.metrics = metrics
        self.store_at = store_at
        self.poll_period = poll_period
        self._started: bool = False
        self.thread = None

    def _collect_samples(self):
        while True:
            if self.stop_event.wait(0):
                logging.debug("Catched stop event!")
                break

            start = time.time()

            for m in self.metrics:
                logging.debug(f"Collecting {m}")
                m.sample()

            elapsed = time.time() - start

            sleep_time = max(self.poll_period - elapsed, 0)
            if sleep_time == 0:
                logging.warning(
                    f"Collecting metrics took longer than poll period: {pp_time(elapsed)} vs {pp_time(self.poll_period)}"  # noqa
                )

            time.sleep(sleep_time)

    def start_thread(self):
        logging.info("Starting collection of metrics")
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self._collect_samples,
        )
        self.thread.start()
        self._started = True

    def stop_thread(self):
        logging.info("Stopping collection of metrics")
        self.stop_event.set()
        self.thread.join()
        self._started = False

    def dump(self):
        logging.info("Saving metrics data...")

        # Create folder structure if not exists
        self.store_at.mkdir(parents=True, exist_ok=True)
        for metric in self.metrics:
            metric.dump(self.store_at)

    def clear_metrics(self):
        for metric in self.metrics:
            metric.clear()

    def __enter__(self):
        if self.metrics:
            self.start_thread()
        return self

    def __exit__(self, *args, **kwargs):
        if self._started:
            self.stop_thread()
            self.dump()
            self.clear_metrics()
