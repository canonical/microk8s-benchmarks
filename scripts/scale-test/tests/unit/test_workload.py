from unittest.mock import patch

from benchmarks.workload import Workload


@patch("benchmarks.workload.time.time", side_effect=[10, 11, 12, 12])
@patch("benchmarks.workload.time.sleep")
def test_wait(_time_sleep, _time_time):

    poll_period = 3
    wkl = Workload(None, duration=2, poll_period=poll_period)
    wkl.wait()

    _time_sleep.assert_called_once_with(poll_period)
