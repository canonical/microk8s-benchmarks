from unittest.mock import Mock

from utils import get_cluster_info, get_unit

from scale_test.metrics import DqliteCPU, DqliteMemory

TEST_UNIT_1 = get_unit(name="unit_1", ip="bar", instance_id="ba")
TEST_UNIT_2 = get_unit(name="unit_2", ip="bar", instance_id="ba")
TEST_CLUSTER_INFO = get_cluster_info(
    model="test",
    master=TEST_UNIT_1,
    control_plane=[TEST_UNIT_1, TEST_UNIT_2],
    workers=[],
)


def test_dqlite_memory_metric():
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        size=2,
    )
    resp_mock = Mock(stdout=b"3\n")
    cluster.run_in_unit.return_value = resp_mock
    metric = DqliteMemory(cluster)

    metric.sample()

    assert metric.samples == [[2, 2, TEST_UNIT_1.name, 3], [2, 2, TEST_UNIT_2.name, 3]]
    assert metric.field_names == ["total_nodes", "control_plane", "node", "memory"]


def test_dqlite_cpu_metric():
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        size=2,
    )
    resp_mock = Mock(stdout=b"5.0\n")
    cluster.run_in_unit.return_value = resp_mock
    metric = DqliteCPU(cluster)

    metric.sample()

    assert metric.samples == [
        [2, 2, TEST_UNIT_1.name, 5.0],
        [2, 2, TEST_UNIT_2.name, 5.0],
    ]
    assert metric.field_names == ["total_nodes", "control_plane", "node", "cpu"]
