import json
import logging
import subprocess
from argparse import ArgumentParser, Namespace
from typing import List

from benchmarks import juju
from benchmarks.models import Cluster, Unit
from benchmarks.utils import timeit

APP_NAME = "microk8s-node"
DEFAULT_CHANNEL = "1.24/stable"

logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)


@timeit
def install_microk8s(model, units: List[Unit], channel=DEFAULT_CHANNEL):
    configure_proxy(units)
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
    for u in units:
        cmd = f"echo {u.ip}\t{u.instance_id} >> /etc/hosts"
        juju.run(cmd, app=APP_NAME).check_returncode()


@timeit
def install_snap(channel: str):
    logging.info("Installing microk8s on all units")
    for cmd, check_returncode in [
        (f"snap install microk8s --classic --channel={channel}", True),
        ("sudo usermod -a -G microk8s ubuntu", True),
        ("sudo chown -f -R ubuntu ~/.kube", False),
        ("sudo newgrp microk8s", True),
        ("microk8s start", True),
        ("microk8s status --wait-ready", True),
    ]:
        resp = juju.run(cmd, app=APP_NAME)
        if check_returncode:
            resp.check_returncode()


@timeit
def configure_proxy(units: List[Unit]):
    logging.info("Configuring proxy settings on units")
    PROXY = "http://squid.internal:3128"
    for cmd in [
        f"echo HTTPS_PROXY={PROXY} >> /etc/environment",
        f"echo HTTP_PROXY={PROXY} >> /etc/environment",
        f"echo https_proxy={PROXY} >> /etc/environment",
        f"echo http_proxy={PROXY} >> /etc/environment",
    ]:
        juju.run(cmd, app=APP_NAME).check_returncode()

    # NO_PROXY settings is unit-specific
    for unit in units:
        NO_PROXY = f"10.1.0.0/16,10.152.183.0/24,127.0.0.1,{unit.ip},{unit.instance_id},10.246.154.0/24"
        for cmd in [
            f"echo no_proxy={NO_PROXY} >> /etc/environment",
            f"echo NO_PROXY={NO_PROXY} >> /etc/environment",
        ]:
            juju.run(cmd, unit=unit.name).check_returncode()


def reboot_and_wait(model):
    """
    Reboots all units in the model and then waits for them to be up.
    """
    logging.info("Rebooting all units")
    cmd = f"timeout 10 juju run -a {APP_NAME} -- reboot".split()
    subprocess.run(cmd)

    logging.info(f"Waiting for {model} model...")
    juju.wait_for_model(model)


def add_node(master) -> List[str]:
    resp = juju.run("microk8s add-node", unit=master.name)
    resp.check_returncode()
    output = resp.stdout.decode().split("\n")
    join_command = [line for line in output if "microk8s join" in line][0]
    return join_command


@timeit
def join_node_to_cluster(master: Unit, node: Unit, as_worker: bool = False):
    logging.info(f"Joining {node} to cluster")
    join_command = add_node(master)
    if as_worker:
        join_command += " --worker"
    juju.run(join_command, unit=node.name).check_returncode()


@timeit
def setup_cluster(control_plane: int, units: List[Unit]) -> Cluster:
    n_workers = len(units) - control_plane
    logging.info(
        f"Setting up a microk8s cluster: {n_workers} workers and {control_plane} control-plane nodes"
    )

    master_node = units[0]
    control_plane -= 1  # master is running control plane already
    cluster = Cluster(master=master_node, control_plane=[master_node], workers=[])
    if len(units) > 1:
        other_nodes = units[1:]
    else:
        other_nodes = []

    for node in other_nodes:
        if control_plane > 0:
            join_node_to_cluster(master_node, node)
            control_plane -= 1
            cluster.control_plane.append(node)
        else:
            join_node_to_cluster(master_node, node, as_worker=True)
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


@timeit
def main():
    args = parse_arguments()
    try:
        units = deploy_units(args.model, args.nodes)
        install_microk8s(args.model, units, channel=args.channel)
        cluster = setup_cluster(args.control_plane, units)
        save_cluster_info(cluster)
    except Exception:
        logging.exception("Unexpected error")
        if args.destroy_on_error:
            logging.warning(f"Destroying model {args.model}")
            juju.destroy_model(args.model)
        raise


if __name__ == "__main__":
    main()
