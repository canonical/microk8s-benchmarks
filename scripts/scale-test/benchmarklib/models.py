import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Unit:
    instance_id: str
    ip: str
    name: str

    def to_dict(self) -> dict:
        return {"instance_id": self.instance_id, "ip": self.ip, "name": self.name}


@dataclass
class ClusterInfo:
    app: str
    model: str
    master: Unit
    workers: List[Unit]
    control_plane: List[Unit]

    def to_dict(self) -> dict:
        return {
            "app": self.app,
            "model": self.model,
            "master": self.master.to_dict(),
            "workers": [u.to_dict() for u in self.workers],
            "control_plane": [u.to_dict() for u in self.control_plane],
        }

    @classmethod
    def from_json(klass, data: Dict[str, str]) -> "ClusterInfo":
        return klass(
            app=data["app"],
            model=data["model"],
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

    @classmethod
    def from_env(klass):
        return klass(
            username=os.environ["DOCKER_USERNAME"],
            password=os.environ["DOCKER_PASSWORD"],
        )


@dataclass
class Addon:
    name: str
    enable_arg: Optional[str] = None
    disable_arg: Optional[str] = None

    @property
    def enable(self) -> str:
        enable_str = self.name
        if self.enable_arg:
            enable_str = f"{enable_str}:{self.enable_arg}"
        return enable_str

    @property
    def disable(self) -> str:
        disable_str = self.name
        if self.disable_arg:
            disable_str = f"{disable_str}:{self.disable_arg}"
        return disable_str
