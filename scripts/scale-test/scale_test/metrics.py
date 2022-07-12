import json
import math
import statistics
from contextlib import contextmanager
from typing import List

from benchmarklib.cluster import Microk8sCluster
from benchmarklib.metrics.base import (
    ConstantField,
    Metric,
    ParametrizedField,
    VariableField,
)
from benchmarklib.utils import timeit


class APIServerLatency(Metric):
    def __init__(self, cluster: Microk8sCluster, apiserver_api=None):
        super().__init__(name="api_server_latency")
        self.cluster = cluster
        self.add_timestamp_field()
        self.add_field(VariableField("total_nodes", self.total_nodes))
        self.add_field(ConstantField("control_plane", self.total_control_plane_nodes))
        self.add_field(
            ParametrizedField(
                name="latency(s)",
                param_name="percentile",
                params=[50, 90, 95, 99],
                callable=self.get_latency_percentiles,
            )
        )
        self.add_field(VariableField("total_requests", self.get_total_requests))
        self._metric_server_ip = apiserver_api
        self._checkpoint_buckets = {}
        self._checkpoint_requests = 0
        self._last_total_requests = 0

    @property
    def total_control_plane_nodes(self) -> int:
        return len(self.cluster.info.control_plane)

    def total_nodes(self) -> int:
        return self.cluster.size

    def get_total_requests(self):
        return self._last_total_requests - self._checkpoint_requests

    def checkpoint(self):
        metrics = self.poll_metrics()
        buckets = self.get_buckets(metrics)
        self._checkpoint_buckets = {k: v for k, v in buckets.items()}
        self._checkpoint_requests = sum(list(buckets.values()))

    @timeit("polling apiserver")
    def poll_metrics(self):
        metric_prefix = "apiserver_request_duration_seconds"
        commands = [
            "apiserver=$(microk8s.kubectl get svc -n default | grep kubernetes | awk '{print $3}')",
            "token=$(cat /var/snap/microk8s/current/credentials/known_tokens.csv | grep admin | awk --field-separator=\",\" '{print $1}')",
            "cert=/var/snap/microk8s/current/certs/ca.crt",
            f'curl --noproxy "*" https://$apiserver:443/metrics -sk -H "Authorization: Bearer $token" --cacert $cert | grep {metric_prefix}',
        ]
        command = ";".join(commands)
        cp_nodes = self.cluster.info.control_plane
        resp = self.cluster.run_in_units(cp_nodes, command, format="json")
        unit_responses = json.loads(resp.stdout)
        all_apiserver_responses = ""
        for resp in unit_responses:
            all_apiserver_responses += resp["Stdout"]
        return all_apiserver_responses

    def get_buckets(self, output):
        buckets = {}
        for line in output.split("\n"):
            if "_bucket" not in line:
                continue

            if 'verb="WATCH"' in line:
                # Skip those requests as they are polluting results
                continue

            bucket = line.split()[0].split("le=")[-1].strip('}"')
            if bucket == "+Inf":
                bucket = math.inf
            else:
                bucket = float(bucket)
            samples = int(line.split()[-1])
            buckets.setdefault(bucket, 0)
            buckets[bucket] += samples

        return buckets

    def parse_latencies(self, buckets):
        # Substract checkpoint values from previous samples
        for latency, value in self._checkpoint_buckets.items():
            buckets[latency] -= value

        # Calculate derivative of cumulative function
        # to get actual number of samples on each bucket
        prev_value = 0
        latencies = {}
        for latency, value in buckets.items():
            latencies[latency] = value - prev_value
            prev_value = value
        return latencies

    def get_latency_percentiles(self, percentiles: List[int]):
        """
        Calls kube-metrics-server endpoint and parses the apiserver request latency metric samples.
        From that, it calculates the specified percentiles.
        """
        metrics = self.poll_metrics()
        buckets = self.get_buckets(metrics)
        latencies = self.parse_latencies(buckets)
        self._last_total_requests = sum(list(buckets.values()))

        # Simulate samples to calculate quantile
        # {0.05: 2, 0.1: 3, 1: 2} -> [0.05, 0.05, 0.1, 0.1, 0.1, 1, 1]
        samples = [
            latency for latency, value in latencies.items() for _ in range(value)
        ]

        # Return requested percentiles
        sampled_percentiles = statistics.quantiles(samples, n=100)

        result = []
        for perc in percentiles:
            index = perc - 1
            value = round(sampled_percentiles[index], 4)
            result.append([perc, value])

        return result

    @contextmanager
    def sample_with_checkpoint(self):
        self.checkpoint()

        yield

        self.sample()
