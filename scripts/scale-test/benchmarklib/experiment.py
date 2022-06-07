import logging
import os
import shutil
from contextlib import ContextDecorator, contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import ConstantField, Metric
from benchmarklib.metrics.collector import MetricsCollector
from benchmarklib.workload import Workload

CURRENT_PATH = Path.cwd()
DATA_LAKE_PATH = CURRENT_PATH.parent.parent / "data"


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
        self.all_workloads_metrics: List[Metric] = []
        self.workload_metrics: Dict[Workload, List[Metric]] = {}

    def register_workloads(self, workloads, metrics: Optional[List[Metric]] = None):
        """
        Register workload. Use metrics param to add specific metrics
        that will only be collected during the execution of this workload.
        """
        if not isinstance(workloads, list):
            workloads = [workloads]

        self.workloads.extend(workloads)
        if metrics:
            for workload in workloads:
                self.workload_metrics.setdefault(workload, []).extend(metrics)

    def register_metrics(self, metrics: List[Metric]):
        """
        These metrics will be collected for all workloads
        """
        self.all_workloads_metrics.extend(metrics)

    def start(self):
        logging.info(f"Started benchmark: {self.name}")
        for workload in self.workloads:
            self.run_workload(workload)

    def get_metrics_for_workload(self, workload: Workload) -> List[Metric]:
        return self.all_workloads_metrics + self.workload_metrics.get(workload, [])

    @property
    def store_metrics_at(self) -> Path:
        return DATA_LAKE_PATH / self.name / self.run_id

    @property
    def run_id(self):
        _id = datetime.today().strftime("%d-%m-%Y")
        return f"run-{_id}"

    def run_workload(self, workload: Workload):
        with self.short_lived_namespace() as ns:
            with WorkloadMetrics(
                workload=workload,
                metrics=self.get_metrics_for_workload(workload),
                poll_period=10,
                store_at=self.store_metrics_at,
            ):
                workload.apply(namespace=ns)
                workload.wait()

    @contextmanager
    def short_lived_namespace(self):
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


class WorkloadMetrics(MetricsCollector):
    def __init__(
        self,
        workload: Workload,
        metrics: List[Metric],
        store_at: Path,
        poll_period: int = 10,
    ):
        # Inject a field (new column in the metric csv file) to specify from which workload the metrics were collected.
        self.workload = workload
        for metric in metrics:
            metric.add_field(ConstantField("workload", self.workload_id))

        super().__init__(metrics=metrics, store_at=store_at, poll_period=poll_period)

    @property
    def workload_id(self):
        return str(self.workload.yaml)


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
        logging.debug(
            f"Backing up existing kube config {self.config_file} --> {tmpdir.name}"
        )
        shutil.move(self.config_file, tmpdir.name)
        return tmpdir

    def recover_config(self, backup_config: NamedTemporaryFile) -> None:
        """
        Recover a previously backed up kube config file to ~/.kube/config
        """
        logging.debug(
            f"Recovering kube config {backup_config.name} -> {self.config_file}"
        )
        shutil.move(backup_config.name, self.config_file)
