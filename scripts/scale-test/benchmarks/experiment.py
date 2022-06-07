import logging
import os
import shutil
from contextlib import ContextDecorator, contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
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
        # TODO: Verify namespace is conformant to: [a-z0-9]([-a-z0-9]*[a-z0-9])?'
        namespace = self.name.replace("_", "-")
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
        with safe_kubeconfig(self.cluster):
            try:
                self.bootstrap()
                self.start()
            except KeyboardInterrupt:
                logging.info("Experiment cancelled! Tearing down cluster...")
            finally:
                self.teardown()


class safe_kubeconfig(ContextDecorator):
    """
    This context manager handles fetching kube config from the current cluster while keeping existing config safe.
    This will probably not be needed once we have a way to merge several microk8s configs into a single config file.
    """

    def __init__(self, cluster: Microk8sCluster, config: Optional[Path] = None):
        self.cluster = cluster
        self.config_file = config if config else Path.home() / ".kube/config"
        self.backup = None

    def __enter__(self):
        self.backup = self.maybe_backup_current_config()
        self.copy_kubeconfig_from_cluster()
        return self

    def __exit__(self, *exc):
        if self.backup:
            self.recover_config(self.backup)

    def copy_kubeconfig_from_cluster(self):
        cluster_kubeconfig = self.cluster.fetch_kubeconfig()
        if not self.config_file.parent.exists():
            os.mkdir(self.config_file.parent)

        with open(self.config_file, mode="w") as f:
            f.write(cluster_kubeconfig)

    def maybe_backup_current_config(self) -> Optional[NamedTemporaryFile]:
        """
        Backup current kube config ~/.kube/config file into a temporary file
        """
        if not self.config_file.exists():
            # Nothing to do
            return

        tmpdir = NamedTemporaryFile(delete=False)
        shutil.move(self.config_file, tmpdir.name)
        return tmpdir

    def recover_config(self, backup_config: NamedTemporaryFile) -> None:
        """
        Recover a previously backed up kube config file to ~/.kube/config
        """
        shutil.move(backup_config.name, self.config_file)
