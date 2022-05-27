import json
import logging
import subprocess
from argparse import ArgumentParser, Namespace
from typing import List

from benchmarks import juju
from benchmarks.constants import DEFAULT_ADD_NODE_TOKEN, DEFAULT_ADD_NODE_TOKEN_TTL
from benchmarks.models import Cluster, Unit
from benchmarks.utils import timeit

APP_NAME = "microk8s-node"
DEFAULT_CHANNEL = "1.24/stable"


LOG_FORMAT = "[%(asctime)s] [%(levelname)8s] --- %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, datefmt=LOG_DATEFMT)


@timeit
def install_microk8s(
    model, units: List[Unit], channel=DEFAULT_CHANNEL, http_proxy: str = None
):
    if http_proxy is not None:
        configure_http_proxy(units, http_proxy)
    reboot_and_wait(model)
    install_snap(channel)
    update_etc_hosts(units)


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
    status_timeout = 60 * 20  # 20 min
    all_commands = [
        f"snap install microk8s --classic --channel={channel}",
        "sudo usermod -a -G microk8s ubuntu",
        "sudo chown -f -R ubuntu ~/.kube",
        "sudo newgrp microk8s",
        f"microk8s status --wait-ready --timeout={status_timeout}",
    ]
    command = ";".join(all_commands)
    juju.run(command, app=APP_NAME).check_returncode()


@timeit
def configure_http_proxy(units: List[Unit], http_proxy: str):
    logging.info("Configuring proxy settings on units")
    proxy_command = ";".join(
        [
            f"echo HTTPS_PROXY={http_proxy} >> /etc/environment",
            f"echo HTTP_PROXY={http_proxy} >> /etc/environment",
            f"echo https_proxy={http_proxy} >> /etc/environment",
            f"echo http_proxy={http_proxy} >> /etc/environment",
        ]
    )
    juju.run(proxy_command, app=APP_NAME).check_returncode()

    # NO_PROXY settings is unit-specific
    for unit in units:
        NO_PROXY = f"10.1.0.0/16,10.152.183.0/24,127.0.0.1,{unit.ip},{unit.instance_id},10.246.154.0/24"
        no_proxy_command = ";".join(
            [
                f"echo no_proxy={NO_PROXY} >> /etc/environment",
                f"echo NO_PROXY={NO_PROXY} >> /etc/environment",
            ]
        )
        juju.run(no_proxy_command, unit=unit.name).check_returncode()


def reboot_and_wait(model):
    """
    Reboots all units in the model and then waits for them to be up.
    """
    logging.info("Rebooting all units")
    cmd = f"timeout 10 juju run -a {APP_NAME} -- reboot".split()
    subprocess.run(cmd)

    logging.info(f"Waiting for {model} model...")
    juju.wait_for_model(model)


def get_join_cluster_url(master) -> str:
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
def deploy_units(model, n_units: int) -> List[Unit]:
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
            args.model, units, channel=args.channel, http_proxy=args.http_proxy
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
