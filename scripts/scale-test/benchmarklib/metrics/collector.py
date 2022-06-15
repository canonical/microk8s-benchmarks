import logging
import queue
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from benchmarklib.metrics.base import Metric
from benchmarklib.utils import pp_time

DEFAULT_POLL_PERIOD = 10


class MetricsCollector:
    """
    Handles the collection of a set of metrics in a separate thread.
    It will dump the collected samples at the specified path with store_at.

    It is to be used as a context manager:

    >>> with MetricsCollector(metrics=metrics, store_at="/path/to/csv/files/"):
    >>>     # Deploy stuff here
    """

    def __init__(
        self,
        metrics: List[Metric],
        store_at: Optional[Path] = None,
        poll_period: Optional[int] = None,
    ):
        self.metrics = metrics
        self.store_at = store_at
        self.poll_period = poll_period or DEFAULT_POLL_PERIOD
        self._started: bool = False
        self.thread = None

    def _collect_serially(self):
        for m in self.metrics:
            m.sample()

    def _collect_in_parallel(self):
        """
        Starts a different thread for samling each metric
        """
        threads = []
        for m in self.metrics:
            thread = Thread(target=m.sample)
            thread.start()
            threads.append(thread)

        # Wait for them to finish
        for thread in threads:
            thread.join()

            # Bubble up any exception that may have occurred
            if thread.child_exception:
                _, exc_obj, _ = thread.child_exception
                raise exc_obj

    def collect_samples(self):
        """
        Collects samples from metrics until the stop event is set
        """
        while True:
            if self.stop_event.wait(0):
                logging.debug("Catched stop event!")
                break

            start = time.time()

            self._collect_in_parallel()

            elapsed = time.time() - start

            sleep_time = self.poll_period - elapsed
            if sleep_time < 0:
                logging.warning(
                    f"Collecting metrics took longer than poll period: {pp_time(elapsed)} vs {pp_time(self.poll_period)}"  # noqa
                )
                continue

            time.sleep(sleep_time)

    def start_thread(self):
        logging.info("Starting collection of metrics")
        self.stop_event = threading.Event()
        self.thread = Thread(
            target=self.collect_samples,
        )
        self.thread.start()
        self._started = True

    def stop_thread(self):
        logging.info("Stopping collection of metrics")
        self.stop_event.set()
        self.thread.join()
        self.thread.maybe_raise_child_exception()
        self._started = False

    def dump(self):
        """
        Dump the collected metrics' samples
        """
        if self.store_at is None:
            logging.warning("Skipping metrics dump: store_at attribute not specified")
            return

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
        if not self._started:
            return

        self.stop_thread()
        self.dump()
        self.clear_metrics()


class Thread(threading.Thread):
    """
    Communicates errors to parent process via a queue
    """

    def __init__(self, *args, **kwargs):
        self.queue = queue.Queue()
        super().__init__(*args, **kwargs)
        self._exception = None

    def run(self):
        try:
            super().run()
        except Exception:
            self.queue.put(sys.exc_info())

    @property
    def child_exception(self):
        if self._exception is None:
            try:
                exc = self.queue.get(block=False)
                self._exception = exc
            except queue.Empty:
                self._exception = None
        return self._exception

    def maybe_raise_child_exception(self):
        if self.child_exception:
            _, exc_obj, _ = self.child_exception
            raise exc_obj
