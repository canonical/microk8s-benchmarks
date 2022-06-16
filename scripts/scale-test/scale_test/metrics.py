import json
from typing import List

# from benchmarklib.utils import timeit
from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import ConstantField, Metric, MultidimensionalField


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
            MultidimensionalField(
                name="memory_KB",
                param_name="node",
                params=self.control_plane_nodes,
                callable=self.get_dqlite_memory,
            )
        )

    @property
    def control_plane_nodes(self) -> List[str]:
        return [node.name for node in self.cluster.info.control_plane]

    # @timeit("get_dqlite_memory")
    def get_dqlite_memory(self, unit_names: List[str]) -> List[int]:
        # Run command on all units in parallel
        command = "pmap -X $(pgrep k8s-dqlite) | tail -n 1 | awk '{print $2}'"
        resp = self.cluster.run_in_units(unit_names, command, format="json")
        output = json.loads(resp.stdout.decode())

        # Parse output
        samples = []
        for element in output:
            unit_name = element["UnitId"]
            value = int(element["Stdout"].strip())
            samples.append([unit_name, value])
        return samples


class DqliteCPU(ClusterMetric):
    def __init__(self, cluster: Microk8sCluster):
        super().__init__(name="dqlite_cpu", cluster=cluster)
        self.add_field(
            MultidimensionalField(
                name="cpu_%",
                param_name="node",
                params=self.control_plane_nodes,
                callable=self.get_dqlite_cpu,
            )
        )

    @property
    def control_plane_nodes(self) -> List[str]:
        return [node.name for node in self.cluster.info.control_plane]

    # @timeit("get_dqlite_cpu")
    def get_dqlite_cpu(self, unit_names: List[str]) -> List[int]:
        # Run command on all units in parallel
        command = (
            "top -b -n 2 -d 0.2 -p $(pgrep k8s-dqlite) | tail -1 | awk '{print $9}'"
        )
        resp = self.cluster.run_in_units(unit_names, command, format="json")
        output = json.loads(resp.stdout.decode())

        # Parse output
        samples = []
        for element in output:
            unit_name = element["UnitId"]
            value = float(element["Stdout"].strip())
            samples.append([unit_name, value])

        return samples
