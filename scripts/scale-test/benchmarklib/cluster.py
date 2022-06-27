import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from benchmarklib.clients import kubectl
from benchmarklib.clients.juju import JujuSession
from benchmarklib.models import ClusterInfo, Unit


class ClusterCommandError(Exception):
    def __init__(self, command, stdout: str, stderr: str):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr


UnitParam = Union[Unit, str]


class Microk8sCluster:
    """
    Handles interactions to the Microk8s cluster
    """

    def __init__(self, info: ClusterInfo):
        self.info = info
        self.juju = JujuSession(model=info.model, app=info.app)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self):
        return (
            f"Microk8sCluster[model={self.info.model}][nodes={self.size}, cp={self.cp}]"
        )

    @classmethod
    def from_file(klass, cluster_file: Path):
        with open(cluster_file, mode="r") as f:
            info = ClusterInfo.from_json(json.loads(f.read()))
            return klass(info)

    @property
    def size(self) -> int:
        return len(self.info.control_plane) + len(self.info.workers)

    @property
    def cp(self) -> int:
        return len(self.info.control_plane)

    def get_master_node(self) -> Unit:
        return self.info.master

    def run_in_unit(self, unit: UnitParam, command: str, format=None):
        unit_name = unit
        if isinstance(unit, Unit):
            unit_name = unit.name

        resp = self.juju.run_in_unit(command, unit=unit_name, format=format)
        try:
            resp.check_returncode()
            return resp
        except subprocess.CalledProcessError as err:
            stderr = resp.stderr.decode().strip()
            stdout = resp.stdout.decode()
            logging.error(f"Error running {command} on {unit_name}: {stderr}")
            raise ClusterCommandError(command, stdout, stderr) from err

    def run_in_units(
        self, units: List[UnitParam], command: str, format: Optional[str] = None
    ):
        unit_names = units
        if isinstance(units[0], Unit):
            unit_names = [unit.name for unit in units]

        resp = self.juju.run_in_units(command, units=unit_names, format=format)
        try:
            resp.check_returncode()
            return resp
        except subprocess.CalledProcessError as err:
            stderr = resp.stderr.decode().strip()
            stdout = resp.stdout.decode()
            logging.error(f"Error running {command} on {unit_names}: {stderr}")
            raise ClusterCommandError(command, stdout, stderr) from err

    def run_in_master_node(self, command: str, format=None):
        return self.run_in_unit(self.get_master_node(), command, format=format)

    def create_namespace(self, name: str) -> None:
        logging.info(f"Creating {name} namespace")
        kubectl.create("ns", name)

    def delete_namespace(self, name: str) -> None:
        logging.info(f"Deleting {name} namespace")
        kubectl.delete("ns", name)

    def enable(self, addons: List[str]) -> None:
        addons = " ".join(addons)
        logging.info(f"Enabling addons: {addons}")
        self.run_in_master_node(f"microk8s enable {addons}")

    def disable(self, addons: List[str]) -> None:
        addons = " ".join(addons)
        logging.info(f"Disabling addon: {addons}")
        self.run_in_master_node(f"microk8s disable {addons}")

    def fetch_kubeconfig(self) -> str:
        logging.info("Fetching kubectl config from cluster")
        resp = self.run_in_master_node("microk8s config")
        return resp.stdout.decode()

    def pods_ready(self, namespace=None) -> bool:
        if namespace:
            resp = kubectl.get("pods", namespace=namespace, format="json")
        else:
            resp = kubectl.get("pods", all_namespaces=True, format="json")

        output = json.loads(resp.stdout)
        for item in output["items"]:
            if item["kind"] != "Pod":
                # Skip kind
                continue
            for status in item["status"]["containerStatuses"]:
                if status["ready"] is False:
                    return False
        return True
