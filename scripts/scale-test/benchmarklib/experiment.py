import logging
import os
from contextlib import ContextDecorator, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import ConstantField, Metric
from benchmarklib.metrics.collector import MetricsCollector
from benchmarklib.models import Addon
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
        required_addons: Optional[List[Addon]] = None,
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

            workload.apply(namespace=ns)

            with WorkloadMetrics(
                workload=workload,
                metrics=self.get_metrics_for_workload(workload),
                store_at=self.store_metrics_at,
            ):
                workload.wait()

    @contextmanager
    def short_lived_namespace(self):
        """
        We deploy workloads on a new temporary namespace so that it is easier
        to cleanup whatever was deployed.
        """
        # TODO: Verify namespace is conformant to: [a-z0-9]([-a-z0-9]*[a-z0-9])?'
        # and if not, raise an error.
        namespace = self.name.replace("_", "-")
        self.cluster.create_namespace(namespace)

        yield namespace

        self.cluster.delete_namespace(namespace)

    def bootstrap(self):
        logging.info("Bootstrapping cluster")
        if len(self.required_addons) > 0:
            addons = [addon.enable for addon in self.required_addons]
            self.cluster.enable(addons)

    def teardown(self):
        logging.info("Cluster teardown")
        for addon in self.required_addons:
            self.cluster.disable([addon.disable])

    def run(self):
        with fetch_kubeconfig(self.cluster):
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
    ):
        self.workload = workload
        self.workload_field = ConstantField("workload", self.workload_id)
        super().__init__(metrics=metrics, store_at=store_at)

    @property
    def workload_id(self):
        return str(self.workload.yaml)

    def __enter__(self):
        super().__enter__()
        # Inject a field (new column in the metric csv file) to specify
        # from which workload the metrics were collected.
        for metric in self.metrics:
            metric.add_field(self.workload_field)
        return self

    def __exit__(self, *exc):
        super().__exit__(self, *exc)
        # Cleanup workload field
        for metric in self.metrics:
            metric.remove_field(self.workload_field)


class fetch_kubeconfig(ContextDecorator):
    """
    This context manager handles fetching kube config from the current cluster.
    Then it sets the KUBECONFIG env variable so that all kubectl commands executed
    are pointing to the right cluster config.
    """

    def __init__(self, cluster: Microk8sCluster, config: Optional[Path] = None):
        self.cluster = cluster
        self._config_file = config

    def __enter__(self):
        self.fetch_kubeconfig_from_cluster()
        os.environ["KUBECONFIG"] = str(self.config_file)
        return self

    def __exit__(self, *exc):
        self.cleanup_kubeconfig()
        os.environ.pop("KUBECONFIG", None)

    @property
    def config_file(self) -> Path:
        if self._config_file is None:
            model = self.cluster.info.model
            self._config_file = Path.home() / ".kube" / f"config_{model}"
        return self._config_file

    def fetch_kubeconfig_from_cluster(self):
        cluster_kubeconfig = self.cluster.fetch_kubeconfig()
        if not self.config_file.parent.exists():
            os.mkdir(self.config_file.parent)

        with open(self.config_file, mode="w") as f:
            f.write(cluster_kubeconfig)

    def cleanup_kubeconfig(self) -> None:
        try:
            os.unlink(self.config_file)
        except FileNotFoundError:
            pass
