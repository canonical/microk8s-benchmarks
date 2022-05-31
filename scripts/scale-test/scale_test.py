#!/usr/bin/python

import argparse
import logging
from pathlib import Path

from benchmarks.benchmark import Benchmark
from benchmarks.cluster import Microk8sCluster
from benchmarks.workload import Workload

MINUTE = 60
WORKLOAD_TIME = 2 * MINUTE

LOG_FORMAT = "[%(asctime)s] [%(levelname)8s] --- %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, datefmt=LOG_DATEFMT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Scale test benchmark", description="Run")
    parser.add_argument(
        "-c",
        "--cluster-file",
        required=True,
        help="Path of the json file with the details of the cluster where to run the experiment",
    )
    parser.add_argument("--debug", action="store_true", help="Increase log verbosity")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.debug:
        logging.root.setLevel(logging.DEBUG)

    cluster = Microk8sCluster.from_file(Path(args.cluster_file))
    scaletest = Benchmark(
        "scale_testing",
        cluster=cluster,
        required_addons=["dns", "hostpath-storage"],  # , "prometheus"],
    )
    scaletest.register_workloads(
        [
            Workload("workloads/stateless.yaml", duration=WORKLOAD_TIME),
            Workload("workloads/stateful.yaml", duration=WORKLOAD_TIME),
            Workload("workloads/ingress.yaml", duration=WORKLOAD_TIME),
        ]
    )
    scaletest.run()


if __name__ == "__main__":
    main()
