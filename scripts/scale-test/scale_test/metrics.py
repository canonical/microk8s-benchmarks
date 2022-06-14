import functools

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import ConstantField, Metric, NodeAwareField
from benchmarklib.models import Unit


class ClusterMetric(Metric):
    def __init__(self, name, cluster: Microk8sCluster):
        super().__init__(name=name)
        self.cluster = cluster
        self.add_field(ConstantField("total_nodes", self.total_nodes))
        self.add_field(ConstantField("control_plane", self.total_control_plane_nodes))

    @property
    def total_control_plane_nodes(self) -> int:
        return len(self.cluster.info.control_plane)

    @property
    def total_nodes(self) -> int:
        return self.cluster.size


class DqliteMemory(ClusterMetric):
    def __init__(self, cluster: Microk8sCluster):
        super().__init__(name="dqlite_memory", cluster=cluster)
        self.add_field(
            NodeAwareField(
                name="memory",
                nodes=self.control_plane_nodes,
                callable=self.get_dqlite_memory,
            )
        )

    @property
    def control_plane_nodes(self):
        return self.cluster.info.control_plane

    def get_dqlite_memory(self, unit: Unit) -> int:
        command = "pmap -X $(pgrep k8s-dqlite) | tail -n 1 | awk '{print $2}'"
        resp = self.cluster.run_in_unit(unit, command)
        return int(resp.stdout.decode().strip())


class DqliteCPU(ClusterMetric):
    def __init__(self, cluster: Microk8sCluster):
        super().__init__(name="dqlite_cpu", cluster=cluster)
        self.add_field(
            NodeAwareField(
                name="cpu", nodes=self.control_plane_nodes, callable=self.get_dqlite_cpu
            )
        )

    @property
    def control_plane_nodes(self):
        return self.cluster.info.control_plane

    def get_dqlite_cpu(self, unit: Unit) -> float:
        command = (
            "top -b -n 2 -d 0.2 -p $(pgrep k8s-dqlite) | tail -1 | awk '{print $9}'"
        )
        resp = self.cluster.run_in_unit(unit, command)
        return float(resp.stdout.decode().strip())
