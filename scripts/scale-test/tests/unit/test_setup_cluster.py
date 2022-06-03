import json
import os
import sys
from unittest.mock import Mock, call, mock_open, patch

import pytest

from benchmarks.constants import DEFAULT_ADD_NODE_TOKEN, DEFAULT_ADD_NODE_TOKEN_TTL
from benchmarks.models import ClusterInfo, DockerCredentials, Unit
from setup_cluster import (
    deploy_units,
    get_docker_credentials,
    get_join_cluster_url,
    get_units,
    install_microk8s,
    join_node_to_cluster,
    main,
    parse_arguments,
    save_cluster_info,
    setup_cluster,
)


@patch.object(sys, "argv", ["setup_cluster", "-c", "4", "-n", "2"])
def test_parse_args_validates_node_params():
    with pytest.raises(ValueError):
        parse_arguments()


@patch.object(sys, "argv", ["setup_cluster", "--destroy-on-error"])
@patch("setup_cluster.deploy_units", side_effect=Exception)
@patch("setup_cluster.juju.destroy_model")
def test_destroys_model_on_error(_destroy_model, _deploy):
    with pytest.raises(Exception):
        main()
    _destroy_model.assert_called_once_with("microk8s")


@patch("setup_cluster.get_units")
@patch("setup_cluster.juju")
def test_deploy_units_deploys_correct_number_of_replicas(_juju, _get_units):
    units = 10

    deploy_units("foobar", units)

    _juju.deploy.assert_called_once()
    _juju.add_unit.assert_called_once_with(units - 1, "microk8s-node")


@patch("setup_cluster.get_units")
@patch("setup_cluster.juju")
def test_deploy_units_skips_add_unit_when_single_node_cluster(_juju, _get_units):
    deploy_units("foobar", 1)

    _juju.deploy.assert_called_once()
    _juju.add_unit.assert_not_called()


@patch("setup_cluster.juju.status")
def test_get_units(_juju_status):
    _juju_status().stdout = b"""{"model":{"name":"microk8s","type":"iaas","controller":"mk8s-testing-controller","cloud":"mk8s-testing","region":"Boston","version":"2.9.29","model-status":{"current":"available","since":"26 May 2022 12:58:26+02:00"},"sla":"unsupported"},"machines":{"0":{"juju-status":{"current":"started","since":"26 May 2022 13:02:29+02:00","version":"2.9.29"},"hostname":"juju-c6c89a-0","dns-name":"10.246.154.108","ip-addresses":["10.246.154.108"],"instance-id":"juju-c6c89a-0","machine-status":{"current":"allocating","message":"powering on","since":"26 May 2022 12:58:46+02:00"},"modification-status":{"current":"idle","since":"26 May 2022 12:58:35+02:00"},"series":"focal","network-interfaces":{"ens192":{"ip-addresses":["10.246.154.108"],"mac-address":"00:50:56:09:5c:07","gateway":"10.246.154.1","is-up":true}},"constraints":"arch=amd64 cores=2 mem=4096M root-disk=40960M","hardware":"arch=amd64 cores=2 mem=4096M root-disk=40960M root-disk-source=vsanDatastore"},"1":{"juju-status":{"current":"started","since":"26 May 2022 13:02:29+02:00","version":"2.9.29"},"hostname":"juju-c6c89a-1","dns-name":"10.246.154.111","ip-addresses":["10.246.154.111"],"instance-id":"juju-c6c89a-1","machine-status":{"current":"allocating","message":"powering on","since":"26 May 2022 12:58:46+02:00"},"modification-status":{"current":"idle","since":"26 May 2022 12:58:35+02:00"},"series":"focal","network-interfaces":{"ens192":{"ip-addresses":["10.246.154.111"],"mac-address":"00:50:56:09:5c:07","gateway":"10.246.154.1","is-up":true}},"constraints":"arch=amd64 cores=2 mem=4096M root-disk=40960M","hardware":"arch=amd64 cores=2 mem=4096M root-disk=40960M root-disk-source=vsanDatastore"}},"applications":{"microk8s-node":{"charm":"ubuntu","series":"focal","os":"ubuntu","charm-origin":"charmhub","charm-name":"ubuntu","charm-rev":19,"charm-channel":"stable","exposed":false,"application-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"units":{"microk8s-node/0":{"workload-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"juju-status":{"current":"idle","since":"26 May 2022 13:02:32+02:00","version":"2.9.29"},"leader":true,"machine":"0","public-address":"10.246.154.108"},"microk8s-node/1":{"workload-status":{"current":"active","since":"26 May 2022 13:02:30+02:00"},"juju-status":{"current":"idle","since":"26 May 2022 13:02:32+02:00","version":"2.9.29"},"leader":false,"machine":"1","public-address":"10.246.154.111"}},"version":"20.04"}},"storage":{},"controller":{"timestamp":"13:03:13+02:00"}}"""  # noqa
    expected_units = [
        Unit(name="microk8s-node/0", ip="10.246.154.108", instance_id="juju-c6c89a-0"),
        Unit(name="microk8s-node/1", ip="10.246.154.111", instance_id="juju-c6c89a-1"),
    ]
    assert get_units() == expected_units


def test_save_cluster_info():
    with patch("setup_cluster.open", mock_open()) as _open:
        unit = Unit(name="foo", ip="bar", instance_id="ba")
        cluster = ClusterInfo(master=unit, control_plane=[unit], workers=[])

        save_cluster_info(cluster)

        _open.assert_called_once_with("cluster.json", "w")
        _open().write.assert_called_once_with(json.dumps(cluster.to_dict()))


@patch("setup_cluster.get_join_cluster_url")
@patch("setup_cluster.join_node_to_cluster")
def test_setup_cluster_joins_correct_number_of_worker_nodes(
    _join_node_to_cluster, _get_join_cluster_url
):
    master_node = Unit(name="master", ip="masterip", instance_id="masterid")
    other_node = Unit(name="node1", ip="node1ip", instance_id="node1id")
    third_node = Unit(name="third", ip="thirdip", instance_id="thirdid")

    # Try with 1/2 control plane nodes
    units = [master_node, other_node]
    cluster = setup_cluster(1, units)

    _get_join_cluster_url.assert_called_once_with(master_node)
    join_url = _get_join_cluster_url.return_value
    _join_node_to_cluster.assert_called_once_with(other_node, join_url, as_worker=True)
    assert cluster.master == master_node
    assert cluster.control_plane == [master_node]
    assert cluster.workers == [other_node]

    # Try now with 2/3 control planes nodes
    units = [master_node, other_node, third_node]
    cluster = setup_cluster(2, units)

    _join_node_to_cluster.assert_has_calls(
        [call(other_node, join_url), call(third_node, join_url, as_worker=True)]
    )
    assert cluster.master == master_node
    assert cluster.control_plane == [master_node, other_node]
    assert cluster.workers == [third_node]


@patch("setup_cluster.juju")
def test_join_node_to_cluster(_juju):
    node = Mock()
    join_url = "joinme"

    join_node_to_cluster(node, join_url)

    _juju.run.assert_called_once_with(f"microk8s join {join_url}", unit=node.name)


@patch("setup_cluster.juju")
def test_join_node_to_cluster_as_worker(_juju):
    node = Mock()
    join_url = "joinme"

    join_node_to_cluster(node, join_url, as_worker=True)

    _juju.run.assert_called_once_with(
        f"microk8s join {join_url} --worker", unit=node.name
    )


@patch("setup_cluster.juju.run")
def test_get_join_cluster_url(_juju_run):
    master = Mock(name="foo")

    join_url = get_join_cluster_url(master)

    assert join_url == f"{master.ip}:25000/{DEFAULT_ADD_NODE_TOKEN}"
    _juju_run.assert_called_once_with(
        f"microk8s add-node --token {DEFAULT_ADD_NODE_TOKEN} --token-ttl {DEFAULT_ADD_NODE_TOKEN_TTL}",
        unit=master.name,
    )


@patch("setup_cluster.wait_microk8s_ready")
@patch("setup_cluster.update_etc_hosts")
@patch("setup_cluster.install_snap")
@patch("setup_cluster.restart_containerd")
@patch("setup_cluster.configure_containerd")
def test_install_microk8s_configures_containerd_only_if_proxy_or_creds_provided(
    _configure_containerd,
    _restart_containerd,
    _install_snap,
    update_etc_hosts,
    _wait_microk8s_ready,
):
    units = []
    http_proxy = "http://myproxy"
    creds = DockerCredentials(username="foo", password="bar")
    install_microk8s(Mock(), units)
    _configure_containerd.assert_not_called()

    install_microk8s(Mock(), units, http_proxy=http_proxy)
    _configure_containerd.assert_called_once_with(None, http_proxy)
    _configure_containerd.reset_mock()

    install_microk8s(Mock(), units, creds=creds)
    _configure_containerd.assert_called_once_with(creds, None)


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
