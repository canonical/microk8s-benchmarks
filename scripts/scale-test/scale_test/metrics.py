import logging
import math
import statistics
import time
from functools import lru_cache
from typing import List

from benchmarklib.cluster import Microk8sCluster, fetch_kubeconfig
from benchmarklib.metrics.base import (
    ConstantField,
    Metric,
    ParametrizedField,
    VariableField,
)
from benchmarklib.utils import timeit


class APIServerLatency(Metric):
    def __init__(self, cluster: Microk8sCluster, metric_server_ip=None):
        super().__init__(name="api_server_latency")
        self.cluster = cluster
        self.add_timestamp_field()
        self.add_field(VariableField("total_nodes", self.total_nodes))
        self.add_field(ConstantField("control_plane", self.total_control_plane_nodes))
        self.add_field(
            ParametrizedField(
                name="latency(s)",
                param_name="percentile",
                params=[50, 95, 99],
                callable=self.get_latency_percentiles,
            )
        )
        self._metric_server_ip = metric_server_ip

    @property
    def metric_server_ip(self):
        if self._metric_server_ip is None:
            self._metric_server_ip = get_metric_server_ip(self.cluster)
        return self._metric_server_ip

    @property
    def total_control_plane_nodes(self) -> int:
        return len(self.cluster.info.control_plane)

    def total_nodes(self) -> int:
        return self.cluster.size

    @timeit("polling metrics server")
    def poll_metrics(self, metric_prefix):
        # Run command on all units in parallel
        command = f"curl --noproxy '*' https://{self.metric_server_ip}:443/metrics -sk | grep {metric_prefix}"
        resp = self.cluster.run_in_master_node(command)
        return resp.stdout.decode()

    def restart_metrics_server(self):
        logging.info("Restarting metrics server")
        commands = [
            "microk8s kubectl scale deploy -n kube-system metrics-server --replicas=0",
            "microk8s kubectl scale deploy -n kube-system metrics-server --replicas=1",
        ]
        resp = self.cluster.run_in_master_node(";".join(commands))
        resp.check_returncode()

        with fetch_kubeconfig(self.cluster):
            max_tries = 30
            tries = 0
            while (
                not self.cluster.pods_ready(namespace="kube-system")
                and tries < max_tries
            ):
                logging.info("Waiting for metrics server to be up")
                time.sleep(5)
                tries += 1

    def get_latency_percentiles(self, percentiles: List[int]):
        """
        Calls kube-metrics-server endpoint and parses the apiserver request latency metric samples.
        From that, it calculates the specified percentiles.
        """
        metric_prefix = "apiserver_request_duration_seconds"
        output = self.poll_metrics(metric_prefix)
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


@lru_cache(maxsize=1)
def get_metric_server_ip(cluster: Microk8sCluster) -> str:
    logging.info("Fetching metrics server service' ip")
    command = "microk8s kubectl get svc -A | grep metrics-server | awk '{print $4}'"
    resp = cluster.run_in_master_node(command)
    resp.check_returncode()
    ip = resp.stdout.decode().strip()
    if ip is None:
        raise ValueError("Could not find ip for metric server")
    return ip
