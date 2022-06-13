from pathlib import Path
from unittest.mock import patch

from benchmarklib.workload import Workload


@patch("benchmarklib.workload.time.time", side_effect=[10, 11, 12, 12])
@patch("benchmarklib.workload.time.sleep")
def test_wait(_time_sleep, _time_time):

    poll_period = 3
    wkl = Workload(Path.cwd(), duration=2, poll_period=poll_period)
    wkl.wait()

    _time_sleep.assert_called_once_with(poll_period)
