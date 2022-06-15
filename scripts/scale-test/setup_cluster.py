#!/usr/bin/python

import json
import logging
import os
import time
from argparse import ArgumentParser, Namespace
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from benchmarklib.clients.juju import JujuSession
from benchmarklib.cluster import Microk8sCluster
from benchmarklib.constants import (
    DEFAULT_ADD_NODE_TOKEN,
    DEFAULT_ADD_NODE_TOKEN_TTL,
    KnownRegistries,
)
from benchmarklib.models import ClusterInfo, DockerCredentials, Unit
from benchmarklib.utils import timeit

APP_NAME = "microk8s-node"
DEFAULT_CHANNEL = "1.24/stable"
LOG_FORMAT = "[%(asctime)s] [%(levelname)8s] --- %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, datefmt=LOG_DATEFMT)


class JujuClusterSetup:
    """
    Setup a microk8s cluster via the juju client
    """

    def __init__(
        self,
        model: str,
        total_nodes: int,
        control_plane_nodes: int,
        channel: str,
        http_proxy: Optional[str] = None,
        creds: Optional[DockerCredentials] = None,
        private_registry: Optional[str] = None,
        app: str = APP_NAME,
    ):
        self.app = app
        self.model = model
        self.juju = JujuSession(model=model, app=APP_NAME)
        self.total_nodes = total_nodes
        self.control_plane_nodes = control_plane_nodes
        self.channel = channel
        self.http_proxy = http_proxy
        self.creds = creds
        self.private_registry = private_registry
        self.units: List[Unit] = []
        self.cluster_info = None

    def install_microk8s(
        self,
        channel: str,
        http_proxy: Optional[str] = None,
        creds: Optional[DockerCredentials] = None,
        private_registry: Optional[str] = None,
    ):
        """
        Installs microk8s snaps on all deployed units.
        It will configure http proxy and containerd settings if specified.
        """
        if http_proxy:
            self.configure_http_proxy(http_proxy)
            self.reboot_and_wait()

        self.install_snap(channel)
        self.update_etc_hosts()

        if creds or private_registry:
            self.configure_containerd(creds, private_registry)

        self.wait_microk8s_ready()

    def configure_http_proxy(self, http_proxy: str):
        logging.info("Configuring proxy settings on units")
        commands = ";".join(
            [
                f"echo HTTPS_PROXY={http_proxy} >> /etc/environment",
                f"echo HTTP_PROXY={http_proxy} >> /etc/environment",
                f"echo https_proxy={http_proxy} >> /etc/environment",
                f"echo http_proxy={http_proxy} >> /etc/environment",
                "local_ip=$(hostname -I | awk '{print $1}')",
                "juju_instance_id=$(grep \"juju\" /etc/hosts | head -n 1 | awk '{print $NF}')",
                'noproxy="10.0.0.0/8,127.0.0.1,${local_ip},${juju_instance_id}"',
                "echo no_proxy=${noproxy} >> /etc/environment",
                "echo NO_PROXY=${noproxy} >> /etc/environment",
            ]
        )
        self.juju.run_in_all_units(commands).check_returncode()

    def reboot_and_wait(self):
        """
        Reboots all units in the model and then waits for them to be up.
        """
        logging.info("Rebooting all units")
        self.juju.run_in_all_units("reboot", timeout="10s")

        logging.info(f"Waiting for {self.model} model...")
        self.juju.wait_for_model()

    def restart_containerd(self):
        cmd = "sudo snap restart microk8s.daemon-containerd"
        self.juju.run_in_all_units(cmd).check_returncode()

    def configure_containerd(self, creds, registry_addr):
        """
        Configure docker credentials if specified.
        """
        if creds:
            self.configure_containerd_credentials(creds)
        if registry_addr:
            self.configure_containerd_registries(registry_addr)
        if creds or registry_addr:
            self.restart_containerd()

    def configure_containerd_mirror(self, registry, private_registry_addr):
        logging.info(f"Configuring registry mirror for {registry}")
        # # /var/snap/microk8s/current/args/certs.d/docker.io/hosts.toml
        # server = "http://my.registry.internal:5000"

        # [host."http://my.registry.internal:5000"]
        # capabilities = ["pull", "resolve"]
        commands = []
        hosts_file = f"/var/snap/microk8s/current/args/certs.d/{registry}/hosts.toml"
        commands.append(f"rm -rf {hosts_file}")
        lines = [
            f'server = \\"{private_registry_addr}\\"',
            f'[host.\\"{private_registry_addr}\\"]',
            'capabilities = [\\"pull\\", \\"resolve\\"]',
        ]
        for line in lines:
            commands.append(f'echo "{line}" >> {hosts_file}')
        cmd = ";".join(commands)
        self.juju.run_in_all_units(cmd).check_returncode()

    def configure_containerd_registries(self, private_registry_addr: str):
        for registry in KnownRegistries:
            self.configure_containerd_mirror(registry.value, private_registry_addr)

    def configure_containerd_credentials(self, creds: DockerCredentials):
        logging.info("Configuring containerd docker credentials")
        containerd_file = "/var/snap/microk8s/current/args/containerd-template.toml"
        lines = [
            '[plugins.\\"io.containerd.grpc.v1.cri\\".registry.configs.\\"registry-1.docker.io\\".auth]',
            f'username = \\"{creds.username}\\"',
            f'password = \\"{creds.password}\\"',
        ]
        cmd = ";".join([f'echo "{line}" >> {containerd_file}' for line in lines])
        self.juju.run_in_all_units(cmd).check_returncode()

    def update_etc_hosts(self):
        """
        Add entries in /etc/hosts of all units for each node in the cluster.
        This is needed as nodes's hostnames need to be resolvable in order for
        the add-node/join process to work.
        """
        logging.info("Adding units hostnames on /etc/hosts")
        command = ";".join(
            [f"echo {u.ip}\t{u.instance_id} >> /etc/hosts" for u in self.units]
        )
        self.juju.run_in_all_units(command).check_returncode()

    def install_snap(self, channel: str):
        logging.info("Installing microk8s on all units")
        all_commands = [
            f"snap install microk8s --classic --channel={channel}",
            "usermod -a -G microk8s ubuntu",
            "chown -f -R ubuntu ~/.kube",
            "newgrp microk8s",
        ]
        command = ";".join(all_commands)
        self.juju.run_in_all_units(command).check_returncode()

    def wait_microk8s_ready(self, timeout_min: int = 10):
        cmd = f"microk8s status --wait-ready --timeout {timeout_min * 60}"
        self.juju.run_in_all_units(cmd).check_returncode()

    def get_join_cluster_url(self, master: Unit) -> str:
        """
        Executes the microk8s add-node command at the master node with a non-expiring fixed token.
        After that, any other node can join the cluster with the returned join url.
        """
        cmd = f"microk8s add-node --token {DEFAULT_ADD_NODE_TOKEN} --token-ttl {DEFAULT_ADD_NODE_TOKEN_TTL}"
        self.juju.run_in_unit(cmd, unit=master.name).check_returncode()
        return f"{master.ip}:25000/{DEFAULT_ADD_NODE_TOKEN}"

    def join_nodes_to_cluster(
        self, nodes: List[Unit], join_url: str, as_worker: bool = False
    ):
        nodes = [node.name for node in nodes]
        join_command = f"microk8s join {join_url}"
        if as_worker:
            join_command += " --worker"
            logging.info(f"Joining worker nodes to cluster: {nodes}")
        else:
            logging.info(f"Joining control plane nodes to cluster: {nodes}")
        resp = self.juju.run_in_units(join_command, units=nodes)
        resp.check_returncode()
        logging.debug(f"Join output: {resp.stdout.decode()[:1000]}")

    def wait_for_nodes_to_join(self, cluster: ClusterInfo, max_wait: int = 5 * 60):
        logging.info("Waiting for nodes to join the cluster...")
        check_period = 30

        start = time.time()
        while True:
            if self.all_nodes_joined(cluster):
                logging.info("All nodes have joined the cluster")
                break

            if (time.time() - start) > max_wait:
                logging.warning("Some nodes haven't joined the cluster yet")
                break

            time.sleep(check_period)

    def all_nodes_joined(self, cluster: ClusterInfo) -> bool:
        """
        Check whether all nodes in the cluster appear as ready
        in the kubectl get nodes command.
        """
        # Get nodes readiness info
        command = "microk8s.kubectl get nodes -o json"
        resp = self.juju.run_in_unit(command, unit=cluster.master.name)
        resp.check_returncode()
        kubectl_get_nodes = json.loads(resp.stdout.decode())

        # Parse output to check that all cluster nodes show up as ready
        cluster_ids = [node.instance_id for node in cluster.nodes]
        for item in kubectl_get_nodes["items"]:
            if item["kind"] != "Node":
                continue

            node_id = item["metadata"]["name"]
            if node_id not in cluster_ids:
                logging.warning(f"Node not known to cluster {node_id}. Ignoring...")
                continue

            is_ready = False
            for condition in item["status"]["conditions"]:
                if (
                    condition["type"] == "Ready"  # noqa
                    and condition["status"] == "True"  # noqa
                    and condition["reason"] == "KubeletReady"  # noqa
                ):
                    is_ready = True
                    break

            if is_ready:
                cluster_ids.remove(node_id)

        if cluster_ids != []:
            logging.debug(f"Some nodes are not ready yet: {','.join(cluster_ids)}")
            return False

        return True

    def form_cluster(self, control_plane: int) -> ClusterInfo:
        units = self.units[:]
        n_workers = len(units) - control_plane
        logging.info(
            f"Setting up a microk8s cluster: {n_workers} workers and {control_plane} control-plane nodes"
        )
        master_node = units.pop(0)
        control_plane -= 1  # master is running control plane already
        cluster = ClusterInfo(
            app=self.app,
            model=self.model,
            master=master_node,
            control_plane=[master_node],
            workers=[],
        )
        if len(units) == 0:
            # Single-node cluster. No nodes to join
            return cluster

        cp_units = units[:control_plane]
        w_units = units[control_plane:]
        join_url = self.get_join_cluster_url(master_node)
        if cp_units:
            self.join_nodes_to_cluster(cp_units, join_url)
            cluster.control_plane.extend(cp_units)
        if w_units:
            self.join_nodes_to_cluster(w_units, join_url, as_worker=True)
            cluster.workers.extend(w_units)

        self.wait_for_nodes_to_join(cluster, max_wait=10 * 60)
        return cluster

    def deploy_units(self, n_units: int) -> List[Unit]:
        logging.info(f"Deploying {n_units} ubuntu charm units")
        self.juju.add_model().check_returncode()
        self.juju.deploy(
            "ubuntu",
            "--series=focal",
            "--constraints=mem=4G cores=2 root-disk=40G",
        ).check_returncode()
        replicas = n_units - 1
        if replicas > 0:
            self.juju.add_units(replicas).check_returncode()
        self.juju.wait_for_model()
        self.units = [Unit(**data) for data in self.juju.get_units()]

    def save_cluster_info(self, cluster: ClusterInfo):
        clusters_path = Path.cwd() / ".clusters"
        clusters_path.mkdir(parents=True, exist_ok=True)

        path = clusters_path / f"{cluster.model}.json"

        logging.info(f"Saving cluster info to {path}")
        with open(path, "w") as f:
            f.write(json.dumps(cluster.to_dict()))

    def cleanup_cluster_info(self, cluster: ClusterInfo):
        clusters_path = Path.cwd() / ".clusters"
        path = clusters_path / f"{cluster.model}.json"
        try:
            os.unlink(path)
        except FileNotFoundError:
            # Not there anymore
            pass

    @contextmanager
    def temporary_cluster(self):
        try:
            cluster_info = self.setup()
            yield cluster_info
        finally:
            self.destroy()

    def setup(self) -> Microk8sCluster:
        worker_nodes = self.total_nodes - self.control_plane_nodes
        logging.info(
            f"Setting up a microk8s (channel={self.channel}) {self.total_nodes}-node cluster (cp={self.control_plane_nodes}, w={worker_nodes})"  # noqa
        )
        self.deploy_units(self.total_nodes)
        self.install_microk8s(
            channel=self.channel,
            http_proxy=self.http_proxy,
            creds=self.creds,
            private_registry=self.private_registry,
        )
        cluster_info = self.form_cluster(self.control_plane_nodes)
        self.save_cluster_info(cluster_info)
        self.cluster_info = cluster_info
        return Microk8sCluster(cluster_info)

    def destroy(self):
        logging.info(f"Destroying cluster in model {self.model}")
        self.juju.destroy_model()
        if self.cluster_info:
            self.cleanup_cluster_info(self.cluster_info)


def get_docker_credentials(
    args: Namespace,
) -> Optional[DockerCredentials]:
    """
    Get docker credentials from arguments or environment variables (in this order).
    """
    if args and (args.docker_username and args.docker_password):
        return DockerCredentials(
            username=args.docker_username,
            password=args.docker_password,
        )
    try:
        return DockerCredentials.from_env()
    except KeyError:
        logging.debug("docker credentials not provided")
        return None


def parse_arguments() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument(
        "--channel",
        type=str,
        default=DEFAULT_CHANNEL,
        help="Microk8s snap channel to install",
    )
    parser.add_argument(
        "-n",
        "--nodes",
        type=int,
        default=1,
        help="Total number of nodes in the cluster",
    )
    parser.add_argument(
        "-c",
        "--control-plane",
        type=int,
        default=1,
        help="Number of nodes running the control plane",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default="microk8s",
        help="Name of the juju model where the cluster is created",
    )
    parser.add_argument(
        "--http-proxy",
        type=str,
        help="Url of the http and https proxy to configure units with",
        default=None,
    )
    parser.add_argument(
        "--destroy-on-error",
        action="store_true",
        help="Will destroy the juju model if an error occurs",
        default=False,
    )
    parser.add_argument("--debug", action="store_true", help="Increase log verbosity")
    parser.add_argument(
        "--docker-username",
        type=str,
        help="Docker username to configure containerd with",
    )
    parser.add_argument(
        "--docker-password",
        type=str,
        help="Docker password to configure containerd with",
    )
    parser.add_argument(
        "--private-registry",
        type=str,
        default=None,
        help="Address of the private docker registry in the form of {scheme}://{ip}:{port}",
    )
    args = parser.parse_args()
    if args.control_plane > args.nodes:
        raise ValueError("--nodes >= --control-plane")

    configure_logging(args.debug)
    return args


def configure_logging(debug: bool = False):
    level = logging.INFO if debug is False else logging.DEBUG
    logging.root.setLevel(level=level)


@timeit("main")
def main():
    args = parse_arguments()
    error = False
    try:
        mgr = JujuClusterSetup(
            model=args.model,
            total_nodes=args.nodes,
            control_plane_nodes=args.control_plane,
            channel=args.channel,
            http_proxy=args.http_proxy,
            creds=get_docker_credentials(args),
            private_registry=args.private_registry,
        )
        mgr.setup()
    except KeyboardInterrupt:
        logging.info("CTRL+C catched! exiting...")
        error = True
    except Exception:
        logging.exception("Unexpected error")
        error = True
        raise
    finally:
        if error and args.destroy_on_error:
            mgr.destroy()


if __name__ == "__main__":
    main()
