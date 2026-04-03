#!/usr/bin/env python3

"""Plot score trends for a selected camera log."""

from __future__ import annotations

import argparse
from pathlib import Path

from matplotlib import pyplot as plt


def load_log(log_path: Path):
    indices, scores, deviances, score_diffs, deviance_diffs = [], [], [], [], []

    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if not parts:
                continue

            indices.append(int(parts[0]))
            if len(parts) == 5:
                scores.append(float(parts[1]))
                deviances.append(float(parts[2]))
                score_diffs.append(float(parts[3]))
                deviance_diffs.append(float(parts[4]))
            else:
                scores.append(0.0)
                deviances.append(0.0)
                score_diffs.append(0.0)
                deviance_diffs.append(0.0)

    return indices, scores, deviances, score_diffs, deviance_diffs


def cli():
    parser = argparse.ArgumentParser(description="Visualise a camera output.log file.")
    parser.add_argument("log_path", help="Path to a camera output.log file")
    args = parser.parse_args()

    log_path = Path(args.log_path)
    indices, scores, deviances, score_diffs, deviance_diffs = load_log(log_path)

    plt.plot(indices, scores, "-r", label="score")
    plt.plot(indices, deviances, "-b", label="deviance")
    plt.plot(indices, score_diffs, "-g", label="diff_score")
    plt.plot(indices, deviance_diffs, "-y", label="diff_deviance")
    plt.title(str(log_path))
    plt.legend(loc="upper right")
    plt.show()


if __name__ == "__main__":
    cli()
