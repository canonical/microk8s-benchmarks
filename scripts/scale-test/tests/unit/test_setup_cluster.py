import copy
import json
import os
import sys
from unittest.mock import Mock, call, mock_open, patch

import pytest
from utils import get_cluster_info, get_unit

from benchmarklib.constants import DEFAULT_ADD_NODE_TOKEN, DEFAULT_ADD_NODE_TOKEN_TTL
from benchmarklib.models import DockerCredentials
from setup_cluster import (
    JujuClusterSetup,
    get_docker_credentials,
    main,
    parse_arguments,
)


def juju_cluster_setup():
    return JujuClusterSetup(
        model="foo",
        total_nodes=2,
        control_plane_nodes=1,
        channel="latest/edge",
        http_proxy="http://proxy.com",
        creds=DockerCredentials(username="foo", password="bar"),
    )


@patch.object(sys, "argv", ["setup_cluster", "-c", "4", "-n", "2"])
def test_parse_args_validates_node_params():
    with pytest.raises(ValueError):
        parse_arguments()


@patch.object(sys, "argv", ["setup_cluster", "--destroy-on-error"])
@patch("setup_cluster.JujuClusterSetup.deploy_units", side_effect=Exception)
@patch("setup_cluster.JujuSession.destroy_model")
def test_destroys_model_on_error(_destroy_model, _deploy):
    with pytest.raises(Exception):
        main()
    _destroy_model.assert_called_once()


@patch("setup_cluster.JujuSession")
def test_deploy_units_deploys_correct_number_of_replicas(_juju):
    units = 10
    mgr = juju_cluster_setup()

    mgr.deploy_units(units)

    mgr.juju.add_model.assert_called_once()
    mgr.juju.deploy.assert_called_once()
    mgr.juju.add_units.assert_called_once_with(units - 1)


@patch("setup_cluster.JujuSession")
def test_deploy_units_skips_add_unit_when_single_node_cluster(_juju):
    mgr = juju_cluster_setup()

    mgr.deploy_units(1)

    mgr.juju.deploy.assert_called_once()
    mgr.juju.add_units.assert_not_called()


def test_save_cluster_info(path_cwd_mock):
    with patch("setup_cluster.open", mock_open()) as _open:
        cluster = get_cluster_info()

        mgr = juju_cluster_setup()
        mgr.save_cluster_info(cluster)

        _open().write.assert_called_once_with(json.dumps(cluster.to_dict()))


@patch("setup_cluster.JujuClusterSetup.all_nodes_joined", return_value=True)
@patch("setup_cluster.JujuClusterSetup.get_join_cluster_url")
@patch("setup_cluster.JujuClusterSetup.join_nodes_to_cluster")
def test_setup_cluster_joins_correct_number_of_worker_nodes(
    _join_nodes_to_cluster, _get_join_cluster_url, _all_nodes_joined
):
    master_node = get_unit()
    other_node = get_unit()
    third_node = get_unit()

    # Try with 1/2 control plane nodes
    units = [master_node, other_node]
    mgr = juju_cluster_setup()
    mgr.units = units

    cluster = mgr.form_cluster(1)

    _get_join_cluster_url.assert_called_once_with(master_node)
    join_url = _get_join_cluster_url.return_value
    _join_nodes_to_cluster.assert_called_once_with(
        [other_node], join_url, as_worker=True
    )
    assert cluster.master == master_node
    assert cluster.control_plane == [master_node]
    assert cluster.workers == [other_node]

    # Try now with 2/3 control planes nodes
    units = [master_node, other_node, third_node]
    mgr = juju_cluster_setup()
    mgr.units = units
    cluster = mgr.form_cluster(2)

    _join_nodes_to_cluster.assert_has_calls(
        [call([other_node], join_url), call([third_node], join_url, as_worker=True)]
    )
    assert cluster.master == master_node
    assert cluster.control_plane == [master_node, other_node]
    assert cluster.workers == [third_node]


@patch("setup_cluster.JujuSession")
def test_join_nodes_to_cluster(_juju):
    node = Mock()
    join_url = "joinme"
    mgr = juju_cluster_setup()

    mgr.join_nodes_to_cluster([node], join_url)

    mgr.juju.run_in_units.assert_called_once_with(
        f"microk8s join {join_url}", units=[node.name]
    )


@patch("setup_cluster.JujuSession")
def test_join_nodes_to_cluster_as_worker(_juju):
    node = Mock()
    join_url = "joinme"
    mgr = juju_cluster_setup()

    mgr.join_nodes_to_cluster([node], join_url, as_worker=True)

    mgr.juju.run_in_units.assert_called_once_with(
        f"microk8s join {join_url} --worker", units=[node.name]
    )


@patch("setup_cluster.JujuSession")
def test_get_join_cluster_url(_juju_run):
    master = Mock(name="foo")
    mgr = juju_cluster_setup()

    join_url = mgr.get_join_cluster_url(master)

    assert join_url == f"{master.ip}:25000/{DEFAULT_ADD_NODE_TOKEN}"
    mgr.juju.run_in_unit.assert_called_once_with(
        f"microk8s add-node --token {DEFAULT_ADD_NODE_TOKEN} --token-ttl {DEFAULT_ADD_NODE_TOKEN_TTL}",
        unit=master.name,
    )


@patch("setup_cluster.JujuClusterSetup.wait_microk8s_ready")
@patch("setup_cluster.JujuClusterSetup.update_etc_hosts")
@patch("setup_cluster.JujuClusterSetup.install_snap")
@patch("setup_cluster.JujuClusterSetup.configure_containerd")
def test_install_microk8s_configures_containerd_iif_provided(
    _configure_containerd,
    _install_snap,
    update_etc_hosts,
    _wait_microk8s_ready,
):
    units = []
    creds = DockerCredentials(username="foo", password="bar")
    mgr = juju_cluster_setup()

    mgr.install_microk8s(units)

    mgr.configure_containerd.assert_not_called()

    mgr.install_microk8s(units, creds=creds)

    mgr.configure_containerd.assert_called_once_with(creds)


@patch("setup_cluster.JujuClusterSetup.wait_microk8s_ready")
@patch("setup_cluster.JujuClusterSetup.update_etc_hosts")
@patch("setup_cluster.JujuClusterSetup.install_snap")
@patch("setup_cluster.JujuClusterSetup.configure_http_proxy")
@patch("setup_cluster.JujuClusterSetup.reboot_and_wait")
def test_install_microk8s_configures_http_proxy_iif_provided(
    _reboot_and_wait,
    _configure_http_proxy,
    _install_snap,
    _update_etc_hosts,
    _wait_microk8s_ready,
):
    mgr = juju_cluster_setup()

    mgr.install_microk8s("")
    mgr.configure_http_proxy.assert_not_called()
    mgr.reboot_and_wait.assert_not_called()

    http_proxy = "http://proxy:3128"
    mgr.install_microk8s("", http_proxy=http_proxy)
    mgr.configure_http_proxy.assert_called_once_with(http_proxy)
    mgr.reboot_and_wait.assert_called_once()


def test_get_docker_credentials():
    not_in_args = Mock(docker_username=None, docker_password=None)

    assert get_docker_credentials(not_in_args) is None

    in_args = Mock(docker_username="foo", docker_password="bar")
    os.environ["DOCKER_USERNAME"] = "baz"
    os.environ["DOCKER_PASSWORD"] = "hello"

    # Args preceed
    assert get_docker_credentials(in_args) == DockerCredentials(
        username="foo", password="bar"
    )

    # Default to env vars
    assert get_docker_credentials(not_in_args) == DockerCredentials(
        username="baz", password="hello"
    )


GET_NODES_JSON = {
    "apiVersion": "v1",
    "items": [
        {
            "kind": "Node",
            "metadata": {"name": "node-0"},
            "status": {
                "conditions": [
                    {"reason": "KubeletReady", "status": "True", "type": "Ready"}
                ]
            },
        },
        {
            "kind": "Node",
            "metadata": {"name": "node-2"},
            "status": {
                "conditions": [
                    {"reason": "KubeletReady", "status": "True", "type": "Ready"}
                ]
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {"name": "node-4"},
            "spec": {},
            "status": {
                "conditions": [
                    {"reason": "KubeletReady", "status": "True", "type": "Ready"}
                ]
            },
        },
        {
            "kind": "Node",
            "metadata": {"name": "node-1"},
            "status": {
                "conditions": [
                    {"reason": "KubeletReady", "status": "True", "type": "Ready"}
                ]
            },
        },
        {
            "kind": "Node",
            "metadata": {"name": "node-3"},
            "status": {
                "conditions": [
                    {"reason": "KubeletReady", "status": "True", "type": "Ready"}
                ]
            },
        },
    ],
}


@patch("setup_cluster.JujuSession.run_in_unit")
def test_all_nodes_joined_true(_juju_run):
    _juju_run.return_value.stdout = json.dumps(GET_NODES_JSON).encode()

    units = [get_unit(instance_id=f"node-{i}", ip="foo", name="bar") for i in range(5)]
    cluster = get_cluster_info(
        model="foo", master=units[0], control_plane=units, workers=[]
    )

    mgr = juju_cluster_setup()

    assert mgr.all_nodes_joined(cluster) is True


@patch("setup_cluster.JujuSession.run_in_unit")
def test_all_nodes_joined_false(_juju_run):
    get_nodes_false_output = copy.deepcopy(GET_NODES_JSON)
    get_nodes_false_output["items"][0]["status"]["conditions"][0]["status"] = "False"
    test_get_nodes_json = json.dumps(get_nodes_false_output).encode()
    _juju_run.return_value.stdout = test_get_nodes_json

    units = [get_unit(instance_id=f"node-{i}", ip="foo", name="bar") for i in range(5)]
    cluster = get_cluster_info(
        model="foo", master=units[0], control_plane=units, workers=[]
    )

    mgr = juju_cluster_setup()
    assert mgr.all_nodes_joined(cluster) is False
