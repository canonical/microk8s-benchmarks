from unittest.mock import Mock

from utils import get_cluster_info, get_unit

from scale_test.metrics import APIServerLatency

TEST_UNIT_1 = get_unit(name="microk8s-node/0")
TEST_UNIT_2 = get_unit(name="microk8s-node/1")
TEST_CLUSTER_INFO = get_cluster_info(
    master=TEST_UNIT_1,
    control_plane=[TEST_UNIT_1, TEST_UNIT_2],
    workers=[],
)


METRICS = """apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.05"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.1"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.15"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.2"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.25"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.3"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.35"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.4"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.45"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.5"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.6"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.7"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.8"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="0.9"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="1"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="1.25"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="1.5"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="1.75"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="2"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="2.5"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="3"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="3.5"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="4"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="4.5"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="5"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="6"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="7"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="8"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="9"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="10"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="15"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="20"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="25"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="30"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="40"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="50"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="60"} 6
apiserver_request_duration_seconds_bucket{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version="",le="+Inf"} 6
apiserver_request_duration_seconds_sum{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version=""} 0.001088356
apiserver_request_duration_seconds_count{component="",dry_run="",group="",resource="",scope="",subresource="/readyz",verb="GET",version=""} 6
"""  # noqa


def test_metric():
    cluster = Mock(
        info=TEST_CLUSTER_INFO,
        size=2,
    )
    resp_mock = Mock(stdout=METRICS.encode())
    cluster.run_in_master_node.return_value = resp_mock
    metric = APIServerLatency(cluster, "metric-server-ip")

    assert metric.field_names == [
        "timestamp",
        "total_nodes",
        "control_plane",
        "percentile",
        "latency(s)",
    ]

    metric.sample()

    assert len(metric.samples) == 3
    assert metric.samples[0][3:] == [50, 0.05]
    assert metric.samples[1][3:] == [95, 0.05]
    assert metric.samples[2][3:] == [99, 0.05]
