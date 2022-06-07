import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from benchmarks.clients import juju, kubectl
from benchmarks.models import ClusterInfo, Unit


class Microk8sCluster:
    """
    Handles interactions to the Microk8s cluster
    """

    def __init__(self, info: Optional[ClusterInfo] = None):
        self.info = info

    @classmethod
    def from_file(klass, cluster_file: Path):
        with open(cluster_file, mode="r") as f:
            info = ClusterInfo.from_json(json.loads(f.read()))
            return klass(info)

    def get_master_node(self) -> Unit:
        return self.info.master

    def run_in_unit(self, unit: Unit, command: str):
        resp = juju.run(command, unit=unit.name)
        try:
            resp.check_returncode()
            return resp
        except subprocess.CalledProcessError:
            stderr = resp.stderr.decode().strip()
            logging.error(f"Error running {command} on {unit.name}: {stderr}")
            raise

    def run_in_master_node(self, command: str):
        return self.run_in_unit(self.get_master_node(), command)

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
