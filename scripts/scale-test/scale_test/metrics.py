import functools

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import ConstantField, Metric, VariableField
from benchmarklib.models import Unit


class DqliteMemory(Metric):
    def __init__(self, cluster: Microk8sCluster):
        super().__init__(name="dqlite_memory")
        self.cluster = cluster
        self.add_field(ConstantField("total_nodes", self.total_nodes))
        self.add_field(ConstantField("control_plane", self.control_plane_nodes))

        # Setup callables for each control plane node
        for cp_node in self.cluster.info.control_plane:
            name = f"memory_{cp_node.name}"
            callable = functools.partial(self.get_dqlite_memory, cp_node)
            field = VariableField(name, callable=callable)
            self.add_field(field)

    @property
    def control_plane_nodes(self):
        return len(self.cluster.info.control_plane)

    @property
    def total_nodes(self):
        return self.cluster.size

    def get_dqlite_memory(self, unit: Unit) -> int:
        command = "pmap -X $(pgrep k8s-dqlite) | tail -n 1 | awk '{print $2}'"
        resp = self.cluster.run_in_unit(unit, command)
        return int(resp.stdout.decode().strip())
