import itertools
from typing import Optional

from benchmarklib.models import DockerCredentials
from scale_test.experiment import run_experiment
from setup_cluster import JujuClusterSetup

CONTROL_PLANE = (1, 3, 5)
TOTAL_NODES = (1, 10, 30, 50, 100)
CHANNEL = "latest/edge"
HTTP_PROXY = "http://squid.internal:3128"


def valid_cluster_shapes():
    product = itertools.product(CONTROL_PLANE, TOTAL_NODES)
    # Filter out shapes where cp < total nodes
    valid_shapes = [(cp, total) for (cp, total) in product if total >= cp]
    return sorted(valid_shapes, key=lambda x: (x[0], x[1]))


def get_docker_credentials() -> Optional[DockerCredentials]:
    try:
        return DockerCredentials.from_env()
    except KeyError:
        return None


def get_model_name(total_nodes, control_plane) -> str:
    return f"uk8s-benchmarks-cluster-{control_plane}-{total_nodes}"


def run_benchmark():
    for (cp_nodes, total_nodes) in valid_cluster_shapes():

        model = get_model_name(total_nodes, cp_nodes)

        # Create a microk8s cluster with juju on a new model
        mgr = JujuClusterSetup(
            model=model,
            total_nodes=total_nodes,
            control_plane_nodes=cp_nodes,
            channel=CHANNEL,
            http_proxy=HTTP_PROXY,
            creds=get_docker_credentials(),
        )
        with mgr.temporary_setup() as cluster:

            # Run scale-test experiment on it
            run_experiment(cluster)


def main():
    run_benchmark()


if __name__ == "__main__":
    main()
