#!/usr/bin/python

import json
import logging
import os
from argparse import ArgumentParser, Namespace
from typing import List, Optional

from benchmarks.clients import juju
from benchmarks.constants import DEFAULT_ADD_NODE_TOKEN, DEFAULT_ADD_NODE_TOKEN_TTL
from benchmarks.models import Cluster, DockerCredentials, Unit
from benchmarks.utils import timeit

APP_NAME = "microk8s-node"
DEFAULT_CHANNEL = "1.24/stable"


LOG_FORMAT = "[%(asctime)s] [%(levelname)8s] --- %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, datefmt=LOG_DATEFMT)


@timeit
def install_microk8s(
    units: List[Unit],
    channel: str = DEFAULT_CHANNEL,
    http_proxy: Optional[str] = None,
    creds: Optional[DockerCredentials] = None,
):
    install_snap(channel)
    update_etc_hosts(units)

    if creds or http_proxy:
        configure_containerd(creds, http_proxy)
        restart_containerd()

    wait_microk8s_ready()


def restart_containerd():
    cmd = "sudo snap restart microk8s.daemon-containerd"
    juju.run(cmd, app=APP_NAME).check_returncode()


def configure_containerd(
    creds: Optional[DockerCredentials] = None, http_proxy: Optional[str] = None
):
    """
    Configure http proxy if specified. Configure docker credentials if
    specified and http_proxy not set - rate limits are not a problem
    behind a http proxy.
    """
    if http_proxy:
        _configure_containerd_proxy(http_proxy)
    elif creds:
        _configure_containerd_credentials(creds)


def _configure_containerd_proxy(http_proxy: str):
    logging.info("Configuring containerd proxy settings")
    containerd_env = "/var/snap/microk8s/current/args/containerd-env"
    commands = ";".join(
        [
            f"echo HTTPS_PROXY={http_proxy} >> {containerd_env}",
            f"echo HTTP_PROXY={http_proxy} >> {containerd_env}",
            "juju_instance_id=$(grep \"juju\" /etc/hosts | head -n 1 | awk '{print $NF}')",
            'noproxy="10.0.0.0/8,127.0.0.0/8,192.168.0.0/16,${juju_instance_id}"',
            f"echo NO_PROXY=${{noproxy}} >> {containerd_env}",
        ]
    )
    juju.run(commands, app=APP_NAME).check_returncode()


def _configure_containerd_credentials(creds: DockerCredentials):
    logging.info("Configuring containerd docker credentials")
    containerd_file = "/var/snap/microk8s/current/args/containerd-template.toml"
    lines = [
        '[plugins.\\"io.containerd.grpc.v1.cri\\".registry.configs.\\"registry-1.docker.io\\".auth]',
        f'username = \\"{creds.username}\\"',
        f'password = \\"{creds.password}\\"',
    ]
    cmd = ";".join([f'echo "{line}" >> {containerd_file}' for line in lines])
    juju.run(cmd, app=APP_NAME).check_returncode()


def restart_microk8s_on_nodes():
    logging.info("Restarting microk8s")
    cmd = ";".join(["microk8s stop", "microk8s start"])
    juju.run(cmd, app=APP_NAME).check_returncode()


def update_etc_hosts(units: List[Unit]):
    """
    Add entries in /etc/hosts of all units for each node in the cluster.
    This is needed as nodes's hostnames need to be resolvable in order for
    the add-node/join process to work.
    """
    logging.info("Adding units hostnames on /etc/hosts")
    command = ";".join([f"echo {u.ip}\t{u.instance_id} >> /etc/hosts" for u in units])
    juju.run(command, app=APP_NAME).check_returncode()


@timeit
def install_snap(channel: str):
    logging.info("Installing microk8s on all units")
    all_commands = [
        f"snap install microk8s --classic --channel={channel}",
        "sudo usermod -a -G microk8s ubuntu",
        "sudo chown -f -R ubuntu ~/.kube",
        "sudo newgrp microk8s",
    ]
    command = ";".join(all_commands)
    juju.run(command, app=APP_NAME).check_returncode()


@timeit
def wait_microk8s_ready(timeout_min: int = 10):
    cmd = f"microk8s status --wait-ready --timeout {timeout_min * 60}"
    juju.run(cmd, app=APP_NAME).check_returncode()


def reboot_and_wait(model: str):
    """
    Reboots all units in the model and then waits for them to be up.
    """
    logging.info("Rebooting all units")
    juju.run("reboot", app=APP_NAME, timeout="10s")

    logging.info(f"Waiting for {model} model...")
    juju.wait_for_model(model)


def get_join_cluster_url(master: Unit) -> str:
    """
    Executes the microk8s add-node command at the master node with a non-expiring fixed token.
    After that, any other node can join the cluster with the returned join url.
    """
    cmd = f"microk8s add-node --token {DEFAULT_ADD_NODE_TOKEN} --token-ttl {DEFAULT_ADD_NODE_TOKEN_TTL}"
    juju.run(cmd, unit=master.name).check_returncode()
    return f"{master.ip}:25000/{DEFAULT_ADD_NODE_TOKEN}"


@timeit
def join_node_to_cluster(node: Unit, join_url: str, as_worker: bool = False):
    logging.info(f"Joining {node} to cluster")
    join_command = f"microk8s join {join_url}"
    if as_worker:
        join_command += " --worker"
    juju.run(join_command, unit=node.name).check_returncode()


@timeit
def setup_cluster(control_plane: int, units: List[Unit]) -> Cluster:
    n_workers = len(units) - control_plane
    logging.info(
        f"Setting up a microk8s cluster: {n_workers} workers and {control_plane} control-plane nodes"
    )
    master_node = units.pop(0)
    control_plane -= 1  # master is running control plane already
    cluster = Cluster(master=master_node, control_plane=[master_node], workers=[])
    if len(units) == 0:
        # Single-node cluster. No nodes to join
        return cluster

    join_url = get_join_cluster_url(master_node)
    for node in units:
        if control_plane > 0:
            join_node_to_cluster(node, join_url)
            control_plane -= 1
            cluster.control_plane.append(node)
        else:
            join_node_to_cluster(node, join_url, as_worker=True)
            cluster.workers.append(node)
    return cluster


def save_cluster_info(cluster: Cluster):
    path = "cluster.json"
    logging.info(f"Saving cluster info to {path}")
    with open(path, "w") as f:
        f.write(json.dumps(cluster.to_dict()))


def get_units() -> List[Unit]:
    """
    Build the list of ubuntu units from the juju status output
    """
    units = []
    status = json.loads(juju.status(format="json").stdout.decode())
    for unit_name, unit_data in status["applications"][APP_NAME]["units"].items():
        ip = unit_data["public-address"]
        machine_id = unit_data["machine"]
        hostname = status["machines"][machine_id]["hostname"]
        units.append(Unit(name=unit_name, instance_id=hostname, ip=ip))
    return units


@timeit
def deploy_units(model: str, n_units: int) -> List[Unit]:
    logging.info(f"Deploying {n_units} ubuntu charm units")
    juju.add_model(model).check_returncode()
    juju.deploy(
        "ubuntu",
        "--series=focal",
        "--constraints=mem=4G cores=2 root-disk=40G",
        APP_NAME,
    ).check_returncode()
    replicas = n_units - 1
    if replicas > 0:
        juju.add_unit(replicas, APP_NAME).check_returncode()
    juju.wait_for_model(model)
    return get_units()


def get_docker_credentials(args: Namespace) -> Optional[DockerCredentials]:
    """
    Get docker credentials from arguments or environment variables (in this order).
    """
    if args.docker_username and args.docker_password:
        return DockerCredentials(
            username=args.docker_username,
            password=args.docker_password,
        )
    elif os.environ.get("DOCKER_USERNAME") and os.environ.get("DOCKER_PASSWORD"):
        logging.debug("docker credentials found from env vars")
        return DockerCredentials(
            username=os.environ["DOCKER_USERNAME"],
            password=os.environ["DOCKER_PASSWORD"],
        )
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
    args = parser.parse_args()
    if args.control_plane > args.nodes:
        raise ValueError("--nodes >= --control-plane")

    configure_logging(args.debug)
    return args


def configure_logging(debug: bool = False):
    level = logging.INFO if debug is False else logging.DEBUG
    logging.root.setLevel(level=level)


def destroy_model(model: str):
    logging.warning(f"Destroying model {model}")
    juju.destroy_model(model)


@timeit
def main():
    args = parse_arguments()
    try:
        units = deploy_units(args.model, args.nodes)
        install_microk8s(
            units,
            channel=args.channel,
            http_proxy=args.http_proxy,
            creds=get_docker_credentials(args),
        )
        cluster = setup_cluster(args.control_plane, units)
        save_cluster_info(cluster)
    except KeyboardInterrupt:
        logging.info("CTRL+C catched! exiting...")
    except Exception:
        logging.exception("Unexpected error")
        raise
    finally:
        if args.destroy_on_error:
            destroy_model(args.model)


if __name__ == "__main__":
    main()
