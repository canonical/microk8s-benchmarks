import logging
import math
import statistics
from typing import List

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import ConstantField, Metric, ParametrizedField


class APIServerLatency(Metric):
    def __init__(self, cluster: Microk8sCluster, metric_server_ip):
        super().__init__(name="api_server_latency")
        self.cluster = cluster
        self.add_timestamp_field()
        self.add_field(ConstantField("total_nodes", self.total_nodes))
        self.add_field(ConstantField("control_plane", self.total_control_plane_nodes))
        self.add_field(
            ParametrizedField(
                name="latency(s)",
                param_name="percentile",
                params=[50, 95, 99],
                callable=self.get_latency_percentiles,
            )
        )
        self.metric_server_ip = metric_server_ip

    @property
    def total_control_plane_nodes(self) -> int:
        return len(self.cluster.info.control_plane)

    @property
    def total_nodes(self) -> int:
        return self.cluster.size

    def get_latency_percentiles(self, percentiles: List[int]):
        """
        Calls kube-metrics-server endpoint and parses the apiserver request latency metric samples.
        From that, it calculates the specified percentiles.
        """
        metric_prefix = "apiserver_request_duration_seconds"
        # Run command on all units in parallel
        command = f"curl --noproxy '*' https://{self.metric_server_ip}:443/metrics -sk | grep {metric_prefix}"
        resp = self.cluster.run_in_master_node(command)
        output = resp.stdout.decode()

        buckets = {}
        total_count = 0
        for line in output.split("\n"):
            if metric_prefix not in line:
                # Ignore
                continue

            if metric_prefix + "_bucket" in line:
                bucket = line.split()[0].split("le=")[-1].strip('}"')
                if bucket == "+Inf":
                    bucket = math.inf
                else:
                    bucket = float(bucket)
                samples = int(line.split()[-1])
                buckets.setdefault(bucket, 0)
                buckets[bucket] += samples

            elif metric_prefix + "_count" in line:
                count = int(line.split()[-1])
                total_count += count

        # Calculate derivative of cumulative function
        prev_bucket = 0
        latencies = {}
        for bucket, value in buckets.items():
            latencies[bucket] = value - prev_bucket
            prev_bucket = value

        # Simulate samples to calculate quantile
        samples = []
        for bucket, value in latencies.items():
            values = [bucket] * value
            samples.extend(values)

        # Return requested percentiles
        sampled_percentiles = statistics.quantiles(samples, n=101)
        result = []
        for perc in percentiles:
            value = round(sampled_percentiles[perc], 4)
            result.append([perc, value])
        return result
