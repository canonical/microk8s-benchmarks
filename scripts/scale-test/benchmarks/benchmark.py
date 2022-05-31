import logging
from typing import List, Optional

from benchmarks.cluster import Microk8sCluster
from benchmarks.workload import Workload


class Benchmark:
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
        n_workloads = len(self.workloads)

        for index, workload in enumerate(self.workloads):
            workload.apply()
            workload.wait()

            is_last_workload = index == n_workloads - 1
            if n_workloads > 1 and not is_last_workload:
                self.cluster.reset()

    def bootstrap(self):
        logging.info("Bootstrapping cluster")
        if len(self.required_addons) > 0:
            self.cluster.enable(self.required_addons)

    def teardown(self):
        logging.info("Cluster teardown")
        self.cluster.reset()
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
