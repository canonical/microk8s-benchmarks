import logging
import time
from contextlib import ContextDecorator


def pp_time(elapsed: int) -> str:
    """
    Pretty-print elapsed time

    >>> pp_time(60*60 + 30*60 + 25)
    '1h30m25s'
    """
    days = elapsed // 86400
    hours = elapsed // 3600 % 24
    minutes = elapsed // 60 % 60
    seconds = elapsed % 60
    final = ""
    for unit, unit_name in [
        (days, "d"),
        (hours, "h"),
        (minutes, "m"),
        (seconds, "s"),
    ]:
        if unit <= 0:
            continue
        final += f"{unit:.0f}{unit_name}"
    return final or "0s"


class timeit(ContextDecorator):
    def __init__(self, func_name):
        self.func_name = func_name

    def __enter__(self):
        self.start = time.time()
        logging.debug(f"{self.func_name} started")

    def __exit__(self, exc_type, exc, exc_tb):
        elapsed = time.time() - self.start
        if exc is not None:
            logging.debug(f"{self.func_name} errored after {pp_time(elapsed)}.")
        else:
            logging.debug(f"{self.func_name} took {pp_time(elapsed)}.")
