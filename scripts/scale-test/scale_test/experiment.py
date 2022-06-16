#!/usr/bin/python

import argparse
import logging
from pathlib import Path

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.experiment import Experiment
from benchmarklib.models import Addon
from benchmarklib.workload import Workload
from scale_test.metrics import DqliteCPU, DqliteMemory

MINUTE = 60
WORKLOAD_TIME = 5 * MINUTE

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


def configure_logging(args: argparse.Namespace) -> None:
    if args.debug:
        logging.root.setLevel(logging.DEBUG)


def get_cluster_dns_server(cluster: Microk8sCluster) -> str:
    logging.info("Getting DNS server from cluster")
    command = "resolvectl status | grep 'Current DNS Server' | awk '{print $4}'"
    resp = cluster.run_in_master_node(command)
    return resp.stdout.decode().strip()


def run_experiment(cluster: Microk8sCluster):
    # Addons
    dns_server = get_cluster_dns_server(cluster)
    dns = Addon(name="dns", enable_arg=dns_server)
    hostpath = Addon(name="hostpath-storage", disable_arg="destroy-storage")
    prometheus = Addon(name="prometheus")

    # Experiment
    scaletest = Experiment(
        "scale-test",
        cluster=cluster,
        required_addons=[dns, hostpath, prometheus],
    )

    # Workloads
    cwd = Path(__file__).parent.resolve()
    workloads = cwd / "workloads"
    stateless = Workload(workloads / "stateless.yaml", duration=WORKLOAD_TIME)
    stateful = Workload(workloads / "stateful.yaml", duration=WORKLOAD_TIME)
    ingress = Workload(workloads / "ingress.yaml", duration=WORKLOAD_TIME)
    scaletest.register_workloads([stateless, stateful, ingress])

    # Metrics
    dqlite_memory = DqliteMemory(cluster)
    dqlite_cpu = DqliteCPU(cluster)
    scaletest.register_metrics([dqlite_memory, dqlite_cpu])

    scaletest.run()


def main():
    args = parse_args()
    configure_logging(args)
    cluster = Microk8sCluster.from_file(Path(args.cluster_file))
    run_experiment(cluster)


if __name__ == "__main__":
    main()
