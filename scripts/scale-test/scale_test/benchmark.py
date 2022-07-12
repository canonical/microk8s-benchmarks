import argparse
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.experiment import fetch_kubeconfig
from benchmarklib.metrics.base import ConstantField
from benchmarklib.models import DockerCredentials
from scale_test.experiment import setup_experiment
from scale_test.metrics import APIServerLatency
from setup_cluster import JujuClusterSetup

CHANNEL = "latest/edge"
HTTP_PROXY = "http://squid.internal:3128"
CURRENT_PATH = Path.cwd()
DATA_LAKE_PATH = CURRENT_PATH.parent.parent / "data"


def get_docker_credentials() -> Optional[DockerCredentials]:
    try:
        return DockerCredentials.from_env()
    except KeyError:
        return None


def get_private_registry() -> str:
    return os.environ.get("REGISTRY")


class AbstractWorkload:
    name = None

    def __init__(self, cluster):
        self.cluster = cluster
        self.sleep_time = 3 * 60

    def wait(self):
        logging.info("Waiting for some time while the workload runs...")
        time.sleep(self.sleep_time)

    def start(self):
        self._start()
        self.wait()

    def _start(self):
        raise NotImplementedError()

    def stop(self):
        logging.info("Stopping workload")


class IdleWorkload(AbstractWorkload):
    name = "idle"

    def __init__(self, cluster):
        super().__init__(cluster)

    def _start(self):
        pass

    def stop(self):
        super().stop()


class KubeBurnerWorkload(AbstractWorkload):
    name = "kubeburner"

    def __init__(self, cluster):
        super().__init__(cluster)
        self.workload_path = CURRENT_PATH / "scale_test/workloads/kube-burner"
        self.kubeconfig = fetch_kubeconfig(self.cluster, cleanup=False)

    def _start(self):
        self.kubeconfig.cleanup_kubeconfig()
        self.kubeconfig.fetch_kubeconfig_from_cluster()
        self.kubeconfig.set()
        subprocess.run("./start-workload.sh", cwd=self.workload_path).check_returncode()

    def stop(self):
        super().stop()
        subprocess.run("./stop-workload.sh", cwd=self.workload_path).check_returncode()
        self.kubeconfig.unset()


def run(workload_klass, reuse=None, model="scaletest"):
    mgr = JujuClusterSetup(
        model=model,
        channel=CHANNEL,
        http_proxy=HTTP_PROXY,
        creds=get_docker_credentials(),
        private_registry=get_private_registry(),
    )
    try:
        if reuse:
            cluster = Microk8sCluster.from_file(reuse)
            mgr.cluster_info = cluster.info
            mgr.juju.model = cluster.info.model
            mgr.model = cluster.info.model
        else:
            cluster = mgr.setup(total_nodes=5, control_plane_nodes=5)

        bootstrap_experiment(cluster)

        import pdb

        pdb.set_trace()

        latency = APIServerLatency(cluster)
        workload = workload_klass(cluster)

        workload_field = ConstantField(name="workload", value=workload.name)
        latency.add_field(workload_field)

        for target_nodes in (1, 5, 10, 20, 30, 40):

            current_nodes = len(mgr.cluster_info.nodes)

            if current_nodes > target_nodes:
                # Already done. Skipping
                continue

            to_add = target_nodes - current_nodes
            if to_add > 0:
                cluster_info = mgr.add_worker_nodes(to_add)
                cluster = Microk8sCluster(cluster_info)
                latency.cluster = cluster
                workload.cluster = cluster

            # with latency.sample_with_checkpoint():
            workload.start()
            workload.stop()
            dump_metric(latency)
    except Exception as ex:
        logging.error(ex)
        raise
    finally:
        pass


def dump_metric(metric, run_name=None):
    if run_name is None:
        run_name = datetime.today().strftime("%d-%m-%Y")

    dump_path = DATA_LAKE_PATH / "scale-test" / run_name
    dump_path.mkdir(parents=True, exist_ok=True)
    metric.dump(dump_path)
    metric.clear()


def bootstrap_experiment(cluster):
    exp = setup_experiment(cluster)
    with fetch_kubeconfig(cluster):
        exp.bootstrap()


def configure_logging():
    # logging.root.setLevel(logging.DEBUG)
    logging.root.setLevel(logging.INFO)


def parse_arguments():
    parser = argparse.ArgumentParser("Scale test benchmark", description="Run")
    parser.add_argument(
        "-w",
        "--workload",
        choices=["idle", "kube-burner"],
        help="Choose which workload to run",
    )
    parser.add_argument(
        "-r",
        "--reuse",
        help="Reuse existing cluster",
        default=False,
    )
    parser.add_argument(
        "-m",
        "--model",
        help="Model",
        default="scaletest",
    )
    return parser.parse_args()


def main():
    configure_logging()
    args = parse_arguments()

    reuse = args.reuse
    if args.workload == "idle":
        run(IdleWorkload, reuse=reuse, model=args.model)
    else:
        run(KubeBurnerWorkload, reuse=reuse, model=args.model)


if __name__ == "__main__":
    main()
