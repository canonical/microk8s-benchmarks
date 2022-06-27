#!/usr/bin/python

import argparse
import logging
from functools import lru_cache
from pathlib import Path

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.experiment import Experiment
from benchmarklib.models import Addon
from benchmarklib.workload import IdleWorkload
from scale_test.metrics import APIServerLatency

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


@lru_cache(maxsize=1)
def get_cluster_dns_server(cluster: Microk8sCluster) -> str:
    logging.info("Getting DNS server from cluster")
    command = "resolvectl status | grep 'Current DNS Server' | awk '{print $4}'"
    resp = cluster.run_in_master_node(command)
    return resp.stdout.decode().strip()


@lru_cache(maxsize=1)
def get_metric_server_ip(cluster: Microk8sCluster) -> str:
    logging.info("Fetching metrics server service' ip")
    command = "microk8s kubectl get svc -A | grep metrics-server | awk '{print $4}'"
    resp = cluster.run_in_master_node(command)
    resp.check_returncode()
    return resp.stdout.decode().strip()


def run_experiment(cluster: Microk8sCluster):
    # Addons
    dns_server = get_cluster_dns_server(cluster)
    dns = Addon(name="dns", enable_arg=dns_server)
    hostpath = Addon(name="hostpath-storage", disable_arg="destroy-storage")
    metrics_server = Addon(name="metrics-server")
    required_addons = [
        dns,
        hostpath,
        metrics_server,
    ]

    # Experiment
    scaletest = Experiment(
        "scale-test",
        cluster=cluster,
        required_addons=required_addons,
        skip_teardown=True,
    )

    # Workloads
    idle = IdleWorkload(duration=WORKLOAD_TIME)
    scaletest.register_workloads([idle])

    # Metrics
    metric_server_ip = get_metric_server_ip(cluster)
    latency = APIServerLatency(cluster, metric_server_ip)
    scaletest.register_metrics([latency])

    scaletest.run()


def main():
    args = parse_args()
    configure_logging(args)
    cluster = Microk8sCluster.from_file(Path(args.cluster_file))
    run_experiment(cluster)


if __name__ == "__main__":
    main()
