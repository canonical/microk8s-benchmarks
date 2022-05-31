import logging

from benchmarks.utils import timeit


def test_timeit_decorator(caplog):
    caplog.set_level(logging.DEBUG)

    @timeit
    def myfunc(a):
        return a + 1

    assert myfunc(1) == 2

    assert len(caplog.records) == 2
    assert caplog.records[0].message == "myfunc started"
    assert "myfunc took" in caplog.records[1].message
