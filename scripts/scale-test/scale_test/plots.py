import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

CURRENT_DIR = Path(__file__).parent.resolve()
SCALE_TEST_DATA = CURRENT_DIR.parent.parent.parent / "data/scale-test"


class RunPlotter:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    def plot(self):
        self.plot_api_server_latency()
        self.plot_api_server_requests()

    def plot_api_server_requests(self):
        samples = self.get_api_server_latency_samples()
        workloads = {s["workload"] for s in samples}

        triples = [
            (s["total_nodes"], s["total_requests"], s["workload"]) for s in samples
        ]

        fig, ax = plt.subplots()
        ax.set(
            ylabel="rate (rpm)",
            xlabel="Cluster size (nodes)",
            title=f"APIServer requests rate",
        )
        ax.grid()
        for workload in sorted(list(workloads)):
            label = workload
            xs = [item[0] for item in triples if item[2] == workload]
            ys = [int(item[1] / 3) for item in triples if item[2] == workload]
            ax.plot(xs, ys, "o--", label=label)
            for i, j in zip(xs, ys):
                ax.annotate(
                    str(j), xy=(i, j), xytext=(-7, 7), textcoords="offset points"
                )
        plt.legend()
        plt.show()

    def plot_api_server_latency(self):
        samples = self.get_api_server_latency_samples()
        workloads = {s["workload"] for s in samples}
        workload_samples = {}

        for workload in workloads:
            workload_samples = [s for s in samples if s["workload"] == workload]
            self.plot_workload_latency(workload, samples=workload_samples)

    def plot_workload_latency(self, workload, samples):
        triples = [(s["total_nodes"], s["percentile"], s["latency"]) for s in samples]
        percentiles = sorted(list({s["percentile"] for s in samples}))

        fig, ax = plt.subplots()
        ax.set(
            ylabel="Latency (ms)",
            xlabel="Cluster size (nodes)",
            title=f"Observed latencies [workload={workload}]",
        )
        # ax.set_yscale("log", base=10)
        ax.grid()

        for percentile in percentiles:
            label = f"p{percentile}"
            xs = [item[0] for item in triples if item[1] == percentile]
            ys = [int(item[2] * 1000) for item in triples if item[1] == percentile]
            ys = [80 if y == math.inf else y for y in ys]
            ax.plot(xs, ys, "o--", label=label)
            for i, j in zip(xs, ys):
                ax.annotate(
                    str(j), xy=(i, j), xytext=(-7, 7), textcoords="offset points"
                )

        plt.legend()
        plt.show()

    def get_api_server_latency_samples(self):
        csvfile = self.run_dir / "metric-api_server_latency.csv"
        with open(csvfile, "r") as f:
            reader = csv.reader(f)
            rows = [row for row in reader]

        # Remove header
        rows.pop(0)
        # Normalize data in list of dicts
        samples = []
        for row in rows:
            samples.append(
                dict(
                    # timestamp=datetime.fromisoformat(row[0]),
                    total_nodes=int(row[0]),
                    control_plane=int(row[1]),
                    percentile=int(row[2]),
                    latency=float(row[3]),
                    total_requests=int(row[4]),
                    workload=row[5],
                )
            )
        return samples


def main(run: str):
    run_path = SCALE_TEST_DATA / run
    rp = RunPlotter(run_path)
    rp.plot()


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--run",
        required=True,
        type=str,
        help="Path to scale-test run to get plots from",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    main(args.run)
