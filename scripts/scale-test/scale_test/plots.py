import argparse
import csv
import statistics as stats
from pathlib import Path

import matplotlib as mp
import matplotlib.pyplot as plt
import numpy as np

CURRENT_DIR = Path(__file__).parent.resolve()
SCALE_TEST_DATA = CURRENT_DIR.parent.parent.parent / "data/scale-test"


class RunPlotter:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    def plot(self):
        self.plot_dqlite_memory()

    def plot_dqlite_memory(self):
        samples = self.get_dqlite_memory_samples()
        workloads = {s["workload"] for s in samples}

        for workload in workloads:
            self.plot_3d_mem(
                workload, samples=[s for s in samples if s["workload"] == workload]
            )

    def plot_3d_mem(self, workload, samples):
        plt.style.use("_mpl-gallery-nogrid")

        # Crunch samples into max averages
        xy = list({(s["total_nodes"], s["control_plane"]) for s in samples})
        xy = sorted(xy, key=lambda x: (x[0], x[1]))

        # averages = {(total_nodes, control_plane): max_average}
        averages = {}
        stds = {}

        for total, cp in xy:
            # Filter subsamples
            ssamples = [
                sample
                for sample in samples
                if sample["total_nodes"] == total and sample["control_plane"] == cp
            ]
            if len(ssamples) == 0:
                continue

            # Group samples by node
            node_samples = {}
            for s in ssamples:
                node_samples.setdefault(s["node"], []).append(s["memory"])

            # Compute averages
            node_averages = [
                (node, sum(vals) / len(vals)) for node, vals in node_samples.items()
            ]

            # Compute std across node averages
            if len(node_averages) <= 1:
                std = 0
            else:
                std = stats.stdev([avg for (_, avg) in node_averages])

            # Get maximum node average
            max_node = max(node_averages, key=lambda x: x[1])

            # Save results
            averages[(total, cp)] = max_node[1]
            stds[(total, cp)] = std

        # Axis
        xyz = [(t, c, m) for (t, c), m in averages.items()]
        X = np.array([x for (x, y, z) in xyz])
        Y = np.array([y for (x, y, z) in xyz])
        Z = np.array([z for (x, y, z) in xyz])

        ax = plt.axes(projection="3d")
        ax.scatter3D(X, Y, Z, c=Z, cmap="gray")
        plt.show()

    def get_dqlite_memory_samples(self):
        dqlite_csv = self.run_dir / "metric-dqlite_memory.csv"
        with open(dqlite_csv, "r") as f:
            reader = csv.reader(f)
            rows = [row for row in reader]
        # Remove header
        rows.pop(0)
        # Normalize data in list of dicts
        samples = []
        for row in rows:
            samples.append(
                dict(
                    total_nodes=int(row[0]),
                    control_plane=int(row[1]),
                    node=row[2],
                    memory=int(row[3]),
                    workload=row[4].split("/")[-1],
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
