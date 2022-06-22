#!/usr/bin/python

import abc
import argparse
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from benchmarklib.clients.juju import JujuSession
from benchmarklib.cluster import Microk8sCluster
from benchmarklib.constants import KnownRegistries
from benchmarklib.models import Addon, Unit
from setup_cluster import JujuClusterSetup, get_docker_credentials

APP = "registry"
MODEL = "registry"
DEFAULT_UK8S_CHANNEL = "latest/edge"
REGISTRY_PORT = 5000
REGISTRY_UNIT_NAME = f"{APP}/0"

DockerImages = Dict[str, str]

DOCKER = "/usr/bin/docker"


def _run_locally(*args):
    cmd = []
    for arg in args:
        cmd.extend(arg.split())
    logging.debug(f"subprocess.run {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True)


class DockerImagePusher(metaclass=abc.ABCMeta):
    def __init__(self, images: DockerImages):
        self.images = images

    def run_commands(self, commands: List[str]):
        raise NotImplementedError()

    @property
    def registry_addr(self):
        raise NotImplementedError()

    def get_image_tag(self, image) -> str:
        # replace registry domain part: docker.io/bar/foo:v1 --> localhost:5000/bar/foo:v1
        for registry in KnownRegistries:
            if image.startswith(registry.value):
                image = image.replace(registry.value + "/", "")
                break
        return f"{self.registry_addr}/{image}"

    def push(self):
        logging.info("Pulling images...")
        pull_commands = []
        for image in self.images:
            pull_commands.append(f"docker pull {image}")
        self.run_commands(pull_commands)

        logging.info("Tagging images...")
        tag_commands = []
        tags = []
        for image in self.images:
            tag = self.get_image_tag(image)
            tags.append(tag)
            tag_commands.append(f"docker tag {image} {tag}")
        self.run_commands(tag_commands)

        # Push them
        logging.info("Pushing images...")
        push_commands = []
        for image_tag in tags:
            push_commands.append(f"docker push {image_tag}")
        self.run_commands(push_commands)


class JujuPusher(DockerImagePusher):
    """
    Pushes docker images to registry via juju
    """

    def __init__(self, images: DockerImages):
        super().__init__(images)
        self.registry_unit = REGISTRY_UNIT_NAME
        self.juju = JujuSession(MODEL, APP)

    def run_commands(self, commands: List[str]):
        juju_command = ";".join(commands)
        self.juju.run_in_unit(*juju_command, unit=self.registry_unit).check_returncode()

    @property
    def registry_addr(self):
        return "localhost:5000"


class LocalPusher(DockerImagePusher):
    """
    Pushes docker images to registry via local docker CLI
    """

    def __init__(self, images: DockerImages, registry_addr: str):
        super().__init__(images)
        self.registry_addr = registry_addr

    def run_commands(self, commands: List[str]):
        for command in commands:
            _run_locally(command).check_returncode()

    @property
    def registry_addr(self):
        return self._registry_addr


class ImageGetter:
    """
    Gets set of images to push to the registry.

    It can read them from a previously saved json file under .docker_images/ or from a cluster.

    It can also deploy a single-node microk8s cluster (with the specified channel) and
    read the downloaded images.
    """

    def __init__(self):
        self.images = None

    def from_cluster(self, cluster: Microk8sCluster) -> DockerImages:
        known_registries = [reg.value for reg in KnownRegistries]
        command = "microk8s.ctr image ls -q"
        resp = cluster.run_in_master_node(command)
        to_parse = resp.stdout.decode()
        images = []
        for line in to_parse.splitlines():
            if ":" not in line or "@sha" in line or line.startswith("sha256:"):
                continue

            registry_found = False
            for registry in known_registries:
                if line.startswith(registry):
                    registry_found = True
                    break

            image = line.strip()
            if not registry_found:
                logging.warning(f"Image not expected: {line}. Skipping...")
            else:
                images.append(image)
        self.images = images
        return images

    def from_file(self, path: Path) -> DockerImages:
        with open(path, "r") as f:
            self.images = json.loads(f.read())
            return self.images

    def save(self, name: str):
        if self.images is None:
            return

        images_path = Path.cwd() / ".docker_images"
        images_path.mkdir(parents=True, exist_ok=True)

        name = name.replace("/", "-")
        path = images_path / f"{name}.json"
        logging.info(f"Saving images to {path}")
        with open(path, "w") as f:
            f.write(json.dumps(self.images))

    def enable_addons_in_cluster(self, cluster):
        """
        We enable the most used addons so that container images are pulled
        """
        dns = Addon(name="dns")
        hostpath = Addon(name="hostpath-storage", disable_arg="destroy-storage")
        prometheus = Addon(name="prometheus")
        all_addons = [
            dns,
            prometheus,
            hostpath,
        ]
        cluster.enable([addon.enable for addon in all_addons])

    def from_snap(self, channel: str, http_proxy: Optional[str] = None) -> DockerImages:
        """
        Setup a temporary microk8s single-node cluster with the specified
        snap channel to dynamically get the list of images to push to the registry
        """
        mgr = JujuClusterSetup(
            model="temp",
            total_nodes=1,
            control_plane_nodes=1,
            channel=channel,
            http_proxy=http_proxy,
            creds=get_docker_credentials(),
        )
        with mgr.temporary_cluster() as cluster:
            self.enable_addons_in_cluster(cluster)
            self.images = self.from_cluster(cluster)
            return self.images


class RegistrySetup:
    """
    Class responsible for setting up a docker registry via juju.
    """

    def __init__(self, http_proxy: Optional[str] = None):
        self.http_proxy = http_proxy
        self.juju = JujuSession(MODEL, APP)
        self.unit = None
        self.registry_addr = None

    def setup(self):
        self.unit = self.deploy_unit()
        if self.http_proxy:
            self.configure_http_proxy(self.http_proxy)
            self.reboot_and_wait()

        logging.info(f"Juju unit for the registry: {self.unit}")
        logging.warning("You will need to setup docker on it manually: ")
        logging.warning(
            f" - Ssh into it with: juju ssh -m {MODEL} -u {REGISTRY_UNIT_NAME}"
        )
        logging.warning(
            " - Install Docker Engine following this guide: https://docs.docker.com/engine/install/ubuntu/"
        )
        logging.warning(
            " - Start the registry following: https://docs.docker.com/registry/"
        )

    @property
    def registry(self) -> str:
        return self.unit.name

    def run_in_unit(self, command):
        self.juju.run_in_unit(command, unit=self.registry).check_returncode()

    def deploy_unit(self) -> Unit:
        logging.info("Deploying ubuntu unit")
        self.juju.add_model().check_returncode()
        self.juju.deploy("ubuntu", "--series=focal").check_returncode()
        self.juju.wait_for_model()
        return self.get_registry_unit()

    def get_registry_unit(self) -> Unit:
        return Unit(**(self.juju.get_units()[0]))

    def reboot_and_wait(self):
        """
        Reboots all units in the model and then waits for them to be up.
        """
        logging.info("Rebooting all units")
        self.juju.run_in_unit("reboot", unit=self.registry, timeout="10s")

        logging.info("Waiting for model...")
        self.juju.wait_for_model()

    def configure_http_proxy(self, http_proxy: str):
        logging.info("Configuring proxy settings")
        command = ";".join(
            [
                f"echo HTTPS_PROXY={http_proxy} >> /etc/environment",
                f"echo HTTP_PROXY={http_proxy} >> /etc/environment",
                f"echo https_proxy={http_proxy} >> /etc/environment",
                f"echo http_proxy={http_proxy} >> /etc/environment",
                "local_ip=$(hostname -I | awk '{print $1}')",
                "juju_instance_id=$(grep \"juju\" /etc/hosts | head -n 1 | awk '{print $NF}')",
                'noproxy="10.0.0.0/8,localhost,127.0.0.1,${local_ip},${juju_instance_id}"',
                "echo no_proxy=${noproxy} >> /etc/environment",
                "echo NO_PROXY=${noproxy} >> /etc/environment",
            ]
        )
        self.run_in_unit(command)


def setup_docker_registry(http_proxy: Optional[str] = None):
    return RegistrySetup(http_proxy).setup()


def push_images(images: DockerImages, registry_addr: Optional[str] = None):
    if registry_addr:
        pusher = LocalPusher(images, registry_addr)
    else:
        pusher = JujuPusher(images)
    pusher.push()


def get_images_from_snap(
    channel: Optional[str] = None, http_proxy: Optional[str] = None
):
    if channel is None:
        channel = DEFAULT_UK8S_CHANNEL

    img_getter = ImageGetter()
    images = img_getter.from_snap(channel, http_proxy)
    img_getter.save(name=channel)
    return images


def get_images_from_file(imagesfile):
    return ImageGetter().from_file(imagesfile)


def get_images_from_cluster(clusterfile):
    cluster = Microk8sCluster.from_file(clusterfile)
    img_getter = ImageGetter()
    images = img_getter.from_cluster(cluster)
    cluster_name = clusterfile.split("/")[-1].split(".")[0]
    img_getter.save(name=cluster_name)
    return images


def parse_arguments():
    parser = argparse.ArgumentParser(prog="setup_registry")
    subparsers = parser.add_subparsers(help="commands")

    # Setup args
    setup_parser = subparsers.add_parser("setup", help="Setup the registry VM")
    setup_parser.add_argument(
        "--http-proxy",
        type=str,
        help="HTTP proxy to setup the units with",
        default=None,
    )
    setup_parser.set_defaults(handler=setup_docker_registry)

    # Push args
    push_parser = subparsers.add_parser("push", help="Push images to the registry")
    group = push_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="Path to images file")
    group.add_argument("--cluster", type=str, help="Path to cluster file")
    group.add_argument(
        "--channel",
        default=None,
        type=str,
        help="Microk8s channel from which to download the images",
    )
    push_parser.add_argument(
        "-r",
        "--registry",
        type=str,
        help="Push images locally to the specified registry. (e.g: http://10.222.111.2:5000)",
        default=None,
    )
    push_parser.set_defaults(handler=push_docker_images)
    return parser.parse_args()


def push_docker_images(args):
    if args.file:
        images = get_images_from_file(args.file)
    elif args.cluster:
        images = get_images_from_cluster(args.cluster)
    else:  # args.channel:
        images = get_images_from_snap(args.channel, args.http_proxy)
    push_images(images, args.registry)


def setup_docker_registry(args):
    RegistrySetup(args.http_proxy).setup()


def main():
    args = parse_arguments()
    args.handler(args)


if __name__ == "__main__":
    main()
