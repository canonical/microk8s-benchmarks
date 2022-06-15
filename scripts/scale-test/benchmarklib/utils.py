import logging
import time


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


class timeit:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        func_name = self.func.__name__
        start = time.time()
        try:
            logging.debug(f"{func_name} started")
            result = self.func(*args, **kwargs)
        except Exception:
            elapsed = int(time.time() - start)
            logging.debug(f"{func_name} errored after {pp_time(elapsed)}.")
            raise
        else:
            elapsed = int(time.time() - start)
            logging.debug(f"{func_name} took {pp_time(elapsed)}.")
            return result
