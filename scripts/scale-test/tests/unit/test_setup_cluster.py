import json
import sys
from unittest.mock import Mock, call, mock_open, patch

import pytest

from benchmarks.models import Cluster, Unit
from setup_cluster import (
    add_node,
    deploy_units,
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
        cluster = Cluster(master=unit, control_plane=[unit], workers=[])

        save_cluster_info(cluster)

        _open.assert_called_once_with("cluster.json", "w")
        _open().write.assert_called_once_with(json.dumps(cluster.to_dict()))


@patch("setup_cluster.join_node_to_cluster")
def test_setup_microk8s_node_correct_number_of_worker_nodes(_join):
    master_node = Unit(name="master", ip="masterip", instance_id="masterid")
    other_node = Unit(name="node1", ip="node1ip", instance_id="node1id")
    third_node = Unit(name="third", ip="thirdip", instance_id="thirdid")

    # Try with 1/2 control plane nodes
    units = [master_node, other_node]
    cluster = setup_cluster(1, units)

    _join.assert_called_once_with(master_node, other_node, as_worker=True)
    assert cluster.master == master_node
    assert cluster.control_plane == [master_node]
    assert cluster.workers == [other_node]

    # Try now with 2/3 control planes nodes
    units = [master_node, other_node, third_node]
    cluster = setup_cluster(2, units)

    _join.assert_has_calls(
        [call(master_node, other_node), call(master_node, third_node, as_worker=True)]
    )
    assert cluster.master == master_node
    assert cluster.control_plane == [master_node, other_node]
    assert cluster.workers == [third_node]


@patch("setup_cluster.juju")
@patch("setup_cluster.add_node")
def test_join_node_to_cluster(_add_node, _juju):
    node = Mock()

    join_node_to_cluster(Mock(), node)

    _juju.run.assert_called_once_with(_add_node.return_value, unit=node.name)


@patch("setup_cluster.juju")
@patch("setup_cluster.add_node", return_value="<join url>")
def test_join_node_to_cluster_as_worker(_add_node, _juju):
    node = Mock()

    join_node_to_cluster(Mock(), node, as_worker=True)

    _juju.run.assert_called_once_with("<join url> --worker", unit=node.name)


@patch("setup_cluster.juju.run")
def test_add_node(_juju_run):
    _juju_run.return_value.stdout = b"""From the node you wish to join to this cluster, run the following:
microk8s join 10.246.154.142:25000/831029c78305abaf849b17dc273ddc0e/f5824339f97e

Use the '--worker' flag to join a node as a worker not running the control plane, eg:
microk8s join 10.246.154.142:25000/831029c78305abaf849b17dc273ddc0e/f5824339f97e --worker

If the node you are adding is not reachable through the default interface you can use one of the following:
microk8s join 10.246.154.142:25000/831029c78305abaf849b17dc273ddc0e/f5824339f97e"""  # noqa

    master = Mock()
    join_command = add_node(master)

    expected_join_command = "microk8s join 10.246.154.142:25000/831029c78305abaf849b17dc273ddc0e/f5824339f97e"
    assert join_command == expected_join_command
    _juju_run.assert_called_once_with("microk8s add-node", unit=master.name)


@patch("setup_cluster.update_etc_hosts")
@patch("setup_cluster.install_snap")
@patch("setup_cluster.reboot_and_wait")
@patch("setup_cluster.configure_http_proxy")
def install_microk8s_configures_http_proxy_only_if_provided(
    _configure_http_proxy, _reboot_and_wait, _install_snap, update_etc_hosts
):
    units = []
    http_proxy = "http://myproxy"
    install_microk8s(Mock(), units)
    _configure_http_proxy.assert_not_called()

    install_microk8s(Mock(), units, http_proxy=http_proxy)
    _configure_http_proxy.assert_called_once_with(units)
