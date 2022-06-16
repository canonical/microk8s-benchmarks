import json
from unittest.mock import Mock

from utils import get_cluster_info, get_unit

from scale_test.metrics import DqliteCPU, DqliteMemory

TEST_UNIT_1 = get_unit(name="microk8s-node/0")
TEST_UNIT_2 = get_unit(name="microk8s-node/1")
TEST_CLUSTER_INFO = get_cluster_info(
    master=TEST_UNIT_1,
    control_plane=[TEST_UNIT_1, TEST_UNIT_2],
    workers=[],
)

MEMORY_RESPONSE = [
    {"Stdout": "382904\n", "UnitId": "microk8s-node/0"},
    {"Stdout": "335856\n", "UnitId": "microk8s-node/1"},
]

CPU_RESPONSE = [
    {"Stdout": "0.5\n", "UnitId": "microk8s-node/0"},
    {"Stdout": "5.0\n", "UnitId": "microk8s-node/1"},
]


def test_dqlite_memory_metric():
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        size=2,
    )
    resp_mock = Mock(stdout=json.dumps(MEMORY_RESPONSE).encode())
    cluster.run_in_units.return_value = resp_mock
    metric = DqliteMemory(cluster)

    metric.sample()

    assert metric.samples == [
        [2, 2, TEST_UNIT_1.name, 382904],
        [2, 2, TEST_UNIT_2.name, 335856],
    ]
    assert metric.field_names == ["total_nodes", "control_plane", "node", "memory_KB"]


def test_dqlite_cpu_metric():
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        size=2,
    )
    resp_mock = Mock(stdout=json.dumps(CPU_RESPONSE).encode())
    cluster.run_in_units.return_value = resp_mock
    metric = DqliteCPU(cluster)

    metric.sample()

    assert metric.samples == [
        [2, 2, TEST_UNIT_1.name, 0.5],
        [2, 2, TEST_UNIT_2.name, 5.0],
    ]
    assert metric.field_names == ["total_nodes", "control_plane", "node", "cpu_%"]
