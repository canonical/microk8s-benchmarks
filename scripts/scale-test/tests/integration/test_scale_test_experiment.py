import sys
from unittest.mock import patch

from scale_test import experiment


def test_main(scale_test_fixtures, cluster_json):
    with patch.object(sys, "argv", ["scale_testing", "-c", cluster_json]):

        experiment.main()
