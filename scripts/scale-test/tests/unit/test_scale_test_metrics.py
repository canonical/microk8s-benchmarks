from unittest.mock import Mock

from benchmarklib.models import ClusterInfo, Unit
from scale_test.metrics import DqliteCPU, DqliteMemory

TEST_UNIT_1 = Unit(name="unit_1", ip="bar", instance_id="ba")
TEST_UNIT_2 = Unit(name="unit_2", ip="bar", instance_id="ba")
TEST_CLUSTER_INFO = ClusterInfo(
    master=TEST_UNIT_1, control_plane=[TEST_UNIT_1, TEST_UNIT_2], workers=[]
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

    assert metric.samples == [[2, 2, 3, 3]]


def test_dqlite_cpu_metric():
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        size=2,
    )
    resp_mock = Mock(stdout=b"5.0\n")
    cluster.run_in_unit.return_value = resp_mock

    metric = DqliteCPU(cluster)
    metric.sample()

    assert metric.samples == [[2, 2, 5.0, 5.0]]
