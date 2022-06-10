from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Unit:
    instance_id: str
    ip: str
    name: str

    def to_dict(self) -> dict:
        return {"instance_id": self.instance_id, "ip": self.ip, "name": self.name}


@dataclass
class ClusterInfo:
    master: Unit
    workers: List[Unit]
    control_plane: List[Unit]

    def to_dict(self) -> dict:
        return {
            "master": self.master.to_dict(),
            "workers": [u.to_dict() for u in self.workers],
            "control_plane": [u.to_dict() for u in self.control_plane],
        }

    @classmethod
    def from_json(klass, data: Dict[str, str]) -> "ClusterInfo":
        return klass(
            master=Unit(**data["master"]),
            control_plane=[Unit(**cp) for cp in data["control_plane"]],
            workers=[Unit(**worker) for worker in data["workers"]],
        )

    @property
    def nodes(self) -> List[Unit]:
        return self.control_plane + self.workers


@dataclass
class DockerCredentials:
    username: str
    password: str
