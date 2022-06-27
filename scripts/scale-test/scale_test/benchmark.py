import itertools
import logging
import os
from typing import Optional

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.models import DockerCredentials
from scale_test.experiment import run_experiment
from setup_cluster import JujuClusterSetup

CHANNEL = "latest/edge"
HTTP_PROXY = "http://squid.internal:3128"


def get_docker_credentials() -> Optional[DockerCredentials]:
    try:
        return DockerCredentials.from_env()
    except KeyError:
        return None


def get_private_registry() -> str:
    return os.environ.get("REGISTRY")


def run_benchmark():
    mgr = JujuClusterSetup(
        model="scale-test",
        channel=CHANNEL,
        http_proxy=HTTP_PROXY,
        creds=get_docker_credentials(),
        private_registry=get_private_registry(),
    )
    try:
        cluster = mgr.setup(total_nodes=5, control_plane_nodes=5)
        for to_add in (0, 5, 10, 20, 20, 20, 20):
            if to_add > 0:
                cluster = mgr.add_worker_nodes(to_add)
            else:
                continue
            run_experiment(cluster)
    finally:
        # mgr.destroy()
        pass


def configure_logging():
    logging.root.setLevel(logging.DEBUG)


def main():
    configure_logging()
    run_benchmark()


if __name__ == "__main__":
    main()
