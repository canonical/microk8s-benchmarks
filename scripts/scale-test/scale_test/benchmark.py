import argparse
import logging
import os
import subprocess
import time
from distutils.command.clean import clean
from pathlib import Path
from typing import Optional
from datetime import datetime

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


class IdleWorkload:
    name = "idle"

    def __init__(self, cluster):
        self.cluster = cluster

    def start(self):
        logging.info("Waiting for 5 minutes while the workload runs...")
        time.sleep(60 * 5)

    def stop(self):
        logging.info("Stopping workload")
        pass


class KubeBurnerWorkload:
    name = "kubeburner"

    def __init__(self, cluster):
        self.cluster = cluster
        self.workload_path = CURRENT_PATH / "scale_test/workloads/kube-burner"
        self.kubeconfig = fetch_kubeconfig(self.cluster, cleanup=False)

    def start(self):
        self.kubeconfig.cleanup_kubeconfig()
        self.kubeconfig.fetch_kubeconfig_from_cluster()
        self.kubeconfig.set()
        subprocess.run("./start-workload.sh", cwd=self.workload_path).check_returncode()
        logging.info("Waiting for 5 minutes while the workload runs...")
        time.sleep(60 * 5)

    def stop(self):
        logging.info("Stopping workload")
        subprocess.run("./stop-workload.sh", cwd=self.workload_path).check_returncode()
        self.kubeconfig.unset()


def run(workload_klass, reuse=False):
    mgr = JujuClusterSetup(
        model="scaletest",
        channel=CHANNEL,
        http_proxy=HTTP_PROXY,
        creds=get_docker_credentials(),
        private_registry=get_private_registry(),
    )
    try:
        if reuse:
            file = input("Enter the path of the cluster file [.clusters/foo.json]: ")
            cluster = Microk8sCluster.from_file(file)
            mgr.cluster_info = cluster.info
            mgr.juju.model = cluster.info.model
            mgr.model = cluster.info.model
        else:
            cluster = mgr.setup(total_nodes=5, control_plane_nodes=5)

        bootstrap_experiment(cluster)

        latency = APIServerLatency(cluster)

        workload = workload_klass(cluster)

        workload_field = ConstantField(name="workload", value=workload.name)
        latency.add_field(workload_field)

        for target_nodes in (5, 10, 20, 40):
            to_add = target_nodes - len(mgr.cluster_info.nodes)
            if to_add > 0:
                cluster = mgr.add_worker_nodes(to_add)
                latency.cluster = cluster
                workload.cluster = cluster

            latency.restart_metrics_server()

            workload.start()

            latency.sample()

            workload.stop()

            dump_metric(latency)
    except Exception as ex:
        logging.error(ex)
        import pdb; pdb.set_trace()
        pass
    finally:
        import pdb; pdb.set_trace()
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
        action="store_true",
        help="Reuse existing cluster",
        default=False,
    )
    return parser.parse_args()


def main():
    configure_logging()
    args = parse_arguments()

    reuse = args.reuse
    if args.workload == "idle":
        run(IdleWorkload, reuse=reuse)
    else:
        run(KubeBurnerWorkload, reuse=reuse)


if __name__ == "__main__":
    main()
