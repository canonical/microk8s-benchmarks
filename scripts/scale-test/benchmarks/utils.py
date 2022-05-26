import logging
import time


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
            logging.debug(
                f"{func_name} errored after {int(time.time()-start)} seconds."
            )
            raise
        else:
            logging.debug(f"{func_name} took {int(time.time()-start)} seconds.")
            return result
