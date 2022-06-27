import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from benchmarklib.experiment import Experiment, fetch_kubeconfig


@patch("benchmarklib.experiment.fetch_kubeconfig", autospec=True)
@patch("benchmarklib.experiment.Experiment.teardown")
def test_run_calls_teardown_on_graceful_exit(_teardown, _fetch_kubeconfig):
    exp = Experiment("foo", Mock())

    exp.run()

    _teardown.assert_called_once()


@patch("benchmarklib.experiment.fetch_kubeconfig", autospec=True)
@patch("benchmarklib.experiment.Experiment.teardown")
@patch("benchmarklib.experiment.Experiment.start")
def test_run_calls_teardown_on_exception(_start, _teardown, _fetch_kubeconfig):
    exp = Experiment("foo", Mock())

    # Unhandled exception
    _start.side_effect = Exception()
    with pytest.raises(Exception):
        exp.run()

    _teardown.assert_called_once()

    # Keyboard interrupt
    _start.side_effect = KeyboardInterrupt()
    _teardown.reset_mock()

    exp.run()

    _teardown.assert_called_once()


def test_cluster_is_reset_between_workloads():
    cluster = Mock()
    exp = Experiment("foo", cluster)
    exp.register_workloads([Mock(), Mock()])

    exp.start()

    assert cluster.create_namespace.call_count == 2
    assert cluster.delete_namespace.call_count == 2


def test_short_lived_namespace():
    cluster = Mock()
    exp = Experiment("foo", cluster)

    with exp.short_lived_namespace() as namespace:
        assert namespace == "foo"
        cluster.create_namespace.assert_called_once_with("foo")
        cluster.delete_namespace.assert_not_called()

    cluster.delete_namespace.assert_called_once_with("foo")


def test_workloads_are_applied_in_namespace():
    cluster = Mock()
    workload = Mock()
    exp = Experiment("foo", cluster)
    exp.run_workload(workload)

    workload.apply.assert_called_once_with(namespace="foo")


@pytest.fixture()
def fake_kube_config():
    config = "previous_config"
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp = tempfile.NamedTemporaryFile(dir=tmpdirname)
        tmp.write(config.encode())
        tmp.file.flush()
        yield Path(tmp.name)

        try:
            tmp.close()
        except FileNotFoundError:
            pass


def test_fetch_kubeconfig(fake_kube_config):
    # Check that config file is computed correctly from model
    cluster = Mock(info=Mock(model="foo-model"))
    fetch = fetch_kubeconfig(cluster)
    assert str(fetch.config_file).endswith(".kube/config_foo-model")

    # Check fetch logic
    cluster = Mock(fetch_kubeconfig=Mock(return_value="new_config"))
    with fetch_kubeconfig(cluster, config=fake_kube_config):

        # Check that cluster kube config was fetched
        cluster.fetch_kubeconfig.assert_called_once()
        with open(fake_kube_config, "r") as f:
            assert f.read() == "new_config"

        assert os.environ["KUBECONFIG"] == str(fake_kube_config)

    # Check cleanup
    assert os.environ.get("KUBECONFIG") is None
    assert not fake_kube_config.exists()


def test_register_metrics():
    exp = Experiment("foo", cluster=Mock())
    workload1 = "workload1"
    workload2 = "workload2"
    workload3 = "workload3"
    workload4 = "workload4"

    metric1 = "metric1"
    metric2 = "metric2"
    metrics_for_all = [metric1, metric2]

    workload1_metric1 = "workload1_metric1"
    workload1_metric2 = "workload1_metric2"
    workload2_metric1 = "workload2_metric1"

    foo_metric = "foo"
    bar_metric = "bar"
    metrics_for_w3_and_w4 = [foo_metric, bar_metric]

    # Register metrics for all workloads
    exp.register_metrics(metrics_for_all)

    # Register workload-specific metrics
    exp.register_workloads(workload1, metrics=[workload1_metric1, workload1_metric2])
    exp.register_workloads(workload2, metrics=[workload2_metric1])

    exp.register_workloads([workload3, workload4], metrics=metrics_for_w3_and_w4)

    assert exp.get_metrics_for_workload(workload1) == [
        metric1,
        metric2,
        workload1_metric1,
        workload1_metric2,
    ]
    assert exp.get_metrics_for_workload(workload2) == [
        metric1,
        metric2,
        workload2_metric1,
    ]
    assert exp.get_metrics_for_workload(workload3) == [
        metric1,
        metric2,
        foo_metric,
        bar_metric,
    ]
