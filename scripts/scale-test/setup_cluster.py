#!/usr/bin/python

import json
import logging
import os
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import List, Optional

from benchmarklib.clients import juju
from benchmarklib.constants import DEFAULT_ADD_NODE_TOKEN, DEFAULT_ADD_NODE_TOKEN_TTL
from benchmarklib.models import ClusterInfo, DockerCredentials, Unit
from benchmarklib.utils import timeit

APP_NAME = "microk8s-node"
DEFAULT_CHANNEL = "1.24/stable"
MINUTE = 60

LOG_FORMAT = "[%(asctime)s] [%(levelname)8s] --- %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, datefmt=LOG_DATEFMT)


@timeit
def install_microk8s(
    model: str,
    units: List[Unit],
    channel: str = DEFAULT_CHANNEL,
    http_proxy: Optional[str] = None,
    creds: Optional[DockerCredentials] = None,
):
    if http_proxy:
        configure_http_proxy(http_proxy)
        reboot_and_wait(model)

    install_snap(channel)
    update_etc_hosts(units)

    if creds:
        configure_containerd(creds)

    wait_microk8s_ready()


@timeit
def configure_http_proxy(http_proxy: str):
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
    juju.run(commands, app=APP_NAME).check_returncode()


def reboot_and_wait(model: str):
    """
    Reboots all units in the model and then waits for them to be up.
    """
    logging.info("Rebooting all units")
    juju.run("reboot", app=APP_NAME, timeout="10s")

    logging.info(f"Waiting for {model} model...")
    juju.wait_for_model(model)


def restart_containerd():
    cmd = "sudo snap restart microk8s.daemon-containerd"
    juju.run(cmd, app=APP_NAME).check_returncode()


def configure_containerd(creds: DockerCredentials):
    """
    Configure docker credentials if specified.
    """
    configure_containerd_credentials(creds)
    restart_containerd()


def configure_containerd_credentials(creds: DockerCredentials):
    logging.info("Configuring containerd docker credentials")
    containerd_file = "/var/snap/microk8s/current/args/containerd-template.toml"
    lines = [
        '[plugins.\\"io.containerd.grpc.v1.cri\\".registry.configs.\\"registry-1.docker.io\\".auth]',
        f'username = \\"{creds.username}\\"',
        f'password = \\"{creds.password}\\"',
    ]
    cmd = ";".join([f'echo "{line}" >> {containerd_file}' for line in lines])
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
        "usermod -a -G microk8s ubuntu",
        "chown -f -R ubuntu ~/.kube",
        "newgrp microk8s",
    ]
    command = ";".join(all_commands)
    juju.run(command, app=APP_NAME).check_returncode()


@timeit
def wait_microk8s_ready(timeout_min: int = 10):
    cmd = f"microk8s status --wait-ready --timeout {timeout_min * 60}"
    juju.run(cmd, app=APP_NAME).check_returncode()


def get_join_cluster_url(master: Unit) -> str:
    """
    Executes the microk8s add-node command at the master node with a non-expiring fixed token.
    After that, any other node can join the cluster with the returned join url.
    """
    cmd = f"microk8s add-node --token {DEFAULT_ADD_NODE_TOKEN} --token-ttl {DEFAULT_ADD_NODE_TOKEN_TTL}"
    juju.run(cmd, unit=master.name).check_returncode()
    return f"{master.ip}:25000/{DEFAULT_ADD_NODE_TOKEN}"


@timeit
def join_nodes_to_cluster(nodes: List[Unit], join_url: str, as_worker: bool = False):
    nodes = [node.name for node in nodes]
    join_command = f"microk8s join {join_url}"
    if as_worker:
        join_command += " --worker"
        logging.info(f"Joining worker nodes to cluster: {nodes}")
    else:
        logging.info(f"Joining control plane nodes to cluster: {nodes}")
    resp = juju.run(join_command, units=nodes)
    resp.check_returncode()
    logging.debug(f"Join output: {resp.stdout.decode()[:1000]}")


@timeit
def wait_for_nodes_to_join(cluster: ClusterInfo, max_wait: int = 5 * MINUTE):
    logging.info("Waiting for nodes to join the cluster...")
    check_period = 30

    start = time.time()
    while True:
        if all_nodes_joined(cluster):
            logging.info("All nodes have joined the cluster")
            break

        if (time.time() - start) > max_wait:
            logging.warning("Some nodes haven't joined the cluster yet")
            break

        time.sleep(check_period)


def all_nodes_joined(cluster: ClusterInfo) -> bool:
    """
    Check whether all nodes in the cluster appear as ready
    in the kubectl get nodes command.
    """
    # Get nodes readiness info
    command = "microk8s.kubectl get nodes -o json"
    resp = juju.run(command, unit=cluster.master.name)
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
        logging.debug(f"Some nodes are not ready yet: {''.join(cluster_ids)}")
        return False

    return True


@timeit
def setup_cluster(control_plane: int, units: List[Unit], model: str) -> ClusterInfo:
    n_workers = len(units) - control_plane
    logging.info(
        f"Setting up a microk8s cluster: {n_workers} workers and {control_plane} control-plane nodes"
    )
    master_node = units.pop(0)
    control_plane -= 1  # master is running control plane already
    cluster = ClusterInfo(
        model=model, master=master_node, control_plane=[master_node], workers=[]
    )
    if len(units) == 0:
        # Single-node cluster. No nodes to join
        return cluster

    cp_units = units[:control_plane]
    w_units = units[control_plane:]
    join_url = get_join_cluster_url(master_node)
    if cp_units:
        join_nodes_to_cluster(cp_units, join_url)
        cluster.control_plane.extend(cp_units)
    if w_units:
        join_nodes_to_cluster(w_units, join_url, as_worker=True)
        cluster.workers.extend(w_units)

    wait_for_nodes_to_join(cluster, max_wait=10 * MINUTE)
    return cluster


def save_cluster_info(cluster: ClusterInfo):
    clusters_path = Path.cwd() / ".clusters"
    path = clusters_path / f"{cluster.model}.json"
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
    model = args.model
    try:
        units = deploy_units(model, args.nodes)
        install_microk8s(
            model,
            units,
            channel=args.channel,
            http_proxy=args.http_proxy,
            creds=get_docker_credentials(args),
        )
        cluster = setup_cluster(args.control_plane, units, model)
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
