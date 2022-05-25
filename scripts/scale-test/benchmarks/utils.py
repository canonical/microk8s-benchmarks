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
            logging.debug(f"{func_name} errored after {time.time()-start}%s seconds.")
            raise
        else:
            logging.debug(f"{func_name} took {time.time()-start}%s seconds.")
            return result
