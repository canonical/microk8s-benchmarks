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
    for shape in sorted(valid_shapes, key=lambda x: (x[1], x[0])):
        yield shape


def get_docker_credentials() -> Optional[DockerCredentials]:
    try:
        return DockerCredentials.from_env()
    except KeyError:
        return None


def get_private_registry() -> Optional[str]:
    return os.environ.get("REGISTRY")


def run_benchmark():
    cluster_shapes = valid_cluster_shapes()
    mgr = JujuClusterSetup(
        model="scale-test",
        channel=CHANNEL,
        http_proxy=HTTP_PROXY,
        creds=get_docker_credentials(),
        private_registry=get_private_registry(),
    )
    try:
        cluster = mgr.setup()
        while True:
            run_experiment(cluster)
            try:
                total_nodes, cp_nodes = next(cluster_shapes)
            except StopIteration:
                break
            cluster = mgr.reshape(total_nodes, cp_nodes)
    finally:
        mgr.destroy()


def configure_logging():
    logging.root.setLevel(logging.DEBUG)


def main():
    configure_logging()
    run_benchmark()


if __name__ == "__main__":
    main()
