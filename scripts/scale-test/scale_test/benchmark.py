import argparse
import itertools
import logging
import multiprocessing as mp
import traceback
from typing import Optional

from benchmarklib.cluster import Microk8sCluster
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
    # Sort by total nodes
    # return sorted(valid_shapes, key=lambda x: x[1])
    # Return only 4 of them for now, as vsphere is struggling with resources
    return sorted(valid_shapes, key=lambda x: x[1])[:4]


def get_docker_credentials() -> Optional[DockerCredentials]:
    try:
        return DockerCredentials.from_env()
    except KeyError:
        return None


def get_model_name(total_nodes, control_plane) -> str:
    return f"uk8s-benchmarks-cluster-{control_plane}-{total_nodes}"


def doit(cp_nodes: int, total_nodes: int, semaphore: mp.BoundedSemaphore):
    """
    Setup a microk8s cluster and run scale test experiment on it.
    """
    with semaphore:
        model = get_model_name(total_nodes, cp_nodes)

        # Create a cluster via Juju and make sure it's deleted on finish
        mgr = JujuClusterSetup(
            model=model,
            total_nodes=total_nodes,
            control_plane_nodes=cp_nodes,
            channel=CHANNEL,
            http_proxy=HTTP_PROXY,
            creds=get_docker_credentials(),
        )
        with mgr.temporary_setup() as cluster_info:

            # Run scale-test experiment on it
            cluster = Microk8sCluster(cluster_info)
            run_experiment(cluster)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--concurrency", type=int, default=1)
    return parser.parse_args()


class Process(mp.Process):
    """
    Subclass multiprocessing.Process to be able to
    catch exceptions of child processes in parent.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pconn, self._cconn = mp.Pipe()
        self._exception = None

    def run(self):
        try:
            super().run()
            self._cconn.send(None)
        except Exception as e:
            tb = traceback.format_exc()
            self._cconn.send((e, tb))
            raise e

    @property
    def exception(self):
        if self._pconn.poll():
            self._exception = self._pconn.recv()
        return self._exception


class ChildProcessException(Exception):
    def __init__(self, child_exc):
        self.child_exc = child_exc


def main(concurrency: int):
    """
    Will run various processes in parallel. Each process will setup a
    cluster in a different juju model and then run the scale test on it.
    """
    semaphore = mp.BoundedSemaphore(concurrency)
    processes = []

    for (cp_nodes, total_nodes) in valid_cluster_shapes():
        proc = Process(target=doit, args=(cp_nodes, total_nodes, semaphore))
        processes.append(proc)
        proc.start()

    try:
        for proc in processes:
            proc.join()

            if proc.exception:
                error, traceback = proc.exception
                logging.exception(f"Error on subprocess. {traceback}")
                raise ChildProcessException(error)
    except KeyboardInterrupt:
        for proc in processes:
            proc.kill()


if __name__ == "__main__":
    args = parse_arguments()
    main(args.concurrency)
