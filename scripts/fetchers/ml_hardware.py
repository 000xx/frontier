"""Refresh the ML hardware frontier from Epoch AI's machine learning hardware data (CC BY 4.0).

Source: https://epoch.ai/data/ml_hardware.csv, linked from Epoch's data page for machine learning hardware
(https://epoch.ai/data/machine-learning-hardware). Each row is one AI accelerator (GPU, TPU or similar) with
its release date and its performance in TFLOP/s at several number formats. A record is the best dense
FP16/BF16 performance of any accelerator released on or before a date, so the line only moves when a
faster chip is released. The records block is rebuilt from the file each time; only facts derived from it
are stored, and the CSV is not copied. DIAG lines show counts, the latest records and every difference from
the frontier file.
"""
import csv
import io
import re

import yaml

from . import common

FRONTIER = "data/frontiers/computing/ml-hardware.yaml"
URL = "https://epoch.ai/data/ml_hardware.csv"
SOURCE = "epoch-ml-hardware"
DIAG_HEADER = True     # discovery run: print the header and first rows before the column check


def fetch():
    raw = common.get(URL).decode("utf-8-sig")
    lines = raw.splitlines()
    print(f"DIAG lines {len(lines)}")
    print(f"DIAG header {lines[0] if lines else ''}")
    for line in lines[1:4]:
        print(f"DIAG sample {line[:400]}")
    raise common.SourceError("discovery run: header printed, no parser yet")
