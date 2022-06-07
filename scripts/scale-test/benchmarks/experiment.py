import logging
from contextlib import contextmanager
from typing import List, Optional

from benchmarks.cluster import Microk8sCluster
from benchmarks.workload import Workload


class Experiment:
    """
    Manages runtime of a benchmark experiment on top of a Microk8s cluster.
    """

    def __init__(
        self,
        name: str,
        cluster: Microk8sCluster,
        required_addons: Optional[List[str]] = None,
    ):
        self.name = name
        self.required_addons = required_addons or []
        self.cluster = cluster
        self.workloads: List[Workload] = []

    def register_workloads(self, workloads):
        self.workloads.extend(workloads)

    def start(self):
        logging.info(f"Started benchmark: {self.name}")
        for workload in self.workloads:
            self.run_workload(workload)

    def run_workload(self, workload: Workload):
        with self.tmp_namespace() as ns:
            workload.apply(namespace=ns)
            workload.wait()

    @contextmanager
    def tmp_namespace(self):
        """
        We deploy workloads on a new temporary namespace to that it is easier to cleanup whatever was deployed.
        """
        namespace = self.name
        self.cluster.create_namespace(namespace)

        yield namespace

        self.cluster.delete_namespace(namespace)

    def bootstrap(self):
        logging.info("Bootstrapping cluster")
        if len(self.required_addons) > 0:
            self.cluster.enable(self.required_addons)

    def teardown(self):
        logging.info("Cluster teardown")
        if len(self.required_addons) > 0:
            self.cluster.disable(self.required_addons)

    def run(self):
        try:
            self.bootstrap()
            self.start()
        except KeyboardInterrupt:
            logging.info("Experiment cancelled! Tearing down cluster...")
        finally:
            self.teardown()
