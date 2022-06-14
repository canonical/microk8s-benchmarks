import sys
from unittest.mock import patch

from scale_test.benchmark import main as benchmark_main
from scale_test.experiment import main as experiment_main


def test_experiment(experiment_fixtures, cluster_json):
    with patch.object(sys, "argv", ["scale_testing", "-c", cluster_json]):
        experiment_main()


def test_benchmark(benchmark_fixtures):
    # serially
    benchmark_main(1)

    # in parallel
    benchmark_main(3)
