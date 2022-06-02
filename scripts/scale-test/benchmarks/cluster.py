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

    def create_namespace(self, name: str):
        logging.info(f"Creating {name} namespace")
        return kubectl.create("ns", name)

    def delete_namespace(self, name: str):
        logging.info(f"Deleting {name} namespace")
        return kubectl.delete("ns", name)

    def enable(self, addons: List[str]):
        addons = " ".join(addons)
        logging.info(f"Enabling addons: {addons}")
        return self.run_in_master_node(f"microk8s enable {addons}")

    def disable(self, addons: List[str]):
        addons = " ".join(addons)
        logging.info(f"Disabling addon: {addons}")
        return self.run_in_master_node(f"microk8s disable {addons}")
