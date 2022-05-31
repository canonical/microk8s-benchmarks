from dataclasses import dataclass
from typing import List


@dataclass
class Unit:
    instance_id: str
    ip: str
    name: str

    def to_dict(self) -> dict:
        return {"instance_id": self.instance_id, "ip": self.ip, "name": self.name}


@dataclass
class Cluster:
    master: Unit
    workers: List[Unit]
    control_plane: List[Unit]

    def to_dict(self) -> dict:
        return {
            "master": self.master.to_dict(),
            "workers": [u.to_dict() for u in self.workers],
            "control_plane": [u.to_dict() for u in self.control_plane],
        }


@dataclass
class DockerCredentials:
    username: str
    password: str
