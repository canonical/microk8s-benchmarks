import sys
from unittest.mock import patch

import setup_cluster


@patch.object(sys, "argv", ["setup_cluster", "--http-proxy", "http://myproxy"])
def test_main(setup_cluster_fixtures):
    setup_cluster.main()
