from unittest.mock import Mock

from benchmarklib.models import ClusterInfo, Unit
from scale_test.metrics import DqliteMemory

TEST_UNIT_1 = Unit(name="unit_1", ip="bar", instance_id="ba")
TEST_UNIT_2 = Unit(name="unit_2", ip="bar", instance_id="ba")
TEST_CLUSTER_INFO = ClusterInfo(
    master=TEST_UNIT_1, control_plane=[TEST_UNIT_1, TEST_UNIT_2], workers=[]
)


def test_dqlite_memory_metric():
    expected_memory = 3
    expected_cluster_size = 2
    expected_control_plane_nodes = 2
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        run_in_unit=Mock(return_value=str(expected_memory)),
        size=2,
    )
    metric = DqliteMemory(cluster)
    metric.sample()
    expected_samples = [
        [
            expected_cluster_size,
            expected_control_plane_nodes,
            expected_memory,
            expected_memory,
        ],
    ]
    assert metric.samples == expected_samples
