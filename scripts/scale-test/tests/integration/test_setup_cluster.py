import sys
from unittest.mock import patch

import setup_cluster


@patch.object(sys, "argv", ["setup_cluster", "--http-proxy", "http://myproxy"])
def test_main(juju_status_mock, subprocess_run_mock):
    setup_cluster.main()
