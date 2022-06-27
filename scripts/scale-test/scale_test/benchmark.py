import itertools
import logging
import os
from typing import Optional

from benchmarklib.models import DockerCredentials
from scale_test.experiment import run_experiment
from setup_cluster import JujuClusterSetup

TOTAL_NODES = (
    5,
    10,
)  # 20, 40, 60, 80, 100)
CONTROL_PLANE = (5,)
CHANNEL = "latest/stable"
HTTP_PROXY = "http://squid.internal:3128"


def valid_cluster_shapes():
    product = itertools.product(CONTROL_PLANE, TOTAL_NODES)
    # Filter out shapes where cp < total nodes
    valid_shapes = [(cp, total) for (cp, total) in product if total >= cp]
    return sorted(valid_shapes, key=lambda x: (x[1], x[0]))


def get_docker_credentials() -> Optional[DockerCredentials]:
    try:
        return DockerCredentials.from_env()
    except KeyError:
        return None


def get_private_registry() -> Optional[str]:
    return os.environ.get("REGISTRY")


def get_model_name(total_nodes, control_plane) -> str:
    return f"uk8s-benchmarks-cluster-{control_plane}-{total_nodes}"


def run_benchmark():
    for (cp_nodes, total_nodes) in valid_cluster_shapes():
        # Create a microk8s cluster with juju on a new model
        mgr = JujuClusterSetup(
            model=get_model_name(total_nodes, cp_nodes),
            total_nodes=total_nodes,
            control_plane_nodes=cp_nodes,
            channel=CHANNEL,
            http_proxy=HTTP_PROXY,
            creds=get_docker_credentials(),
            private_registry=get_private_registry(),
        )
        with mgr.temporary_cluster() as cluster:
            run_experiment(cluster)


def configure_logging():
    logging.root.setLevel(logging.DEBUG)


def main():
    configure_logging()
    run_benchmark()


if __name__ == "__main__":
    main()
