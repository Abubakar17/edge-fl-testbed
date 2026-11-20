"""Analysis of Phase 1 benchmark runs: loading, run selection, raw-link floor, model fit.

Numbers only (numpy), no plotting, so it is testable and reusable: the fitted
latency-bandwidth model is what later phases use to predict communication time.

Key ideas
---------
Raw-link floor
    The fastest an echo could possibly be on a given link, from the baseline
    measurements: one ping round trip plus the payload's transfer time in each
    direction at the iperf3 TCP rate. Everything above the floor is overhead added by
    gRPC, protobuf, Python and the CPUs.

Latency-bandwidth model
    ``time = alpha + bits / bandwidth``. ``alpha`` is the fixed cost of one call
    (software + network latency); ``bandwidth`` is the effective rate for bulk data.
    Standard in distributed computing; two numbers that summarise a whole sweep.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REQUIRED_FILES = ("meta.json", "summary.csv")
# Raw sample file per benchmark mode (echo keeps its original name for older runs).
RAW_FILES = {"echo": "rtt_raw.csv", "upload": "upload_raw.csv", "download": "download_raw.csv"}


# --------------------------------------------------------------------------- loading
@dataclass
class Run:
    """One benchmark run folder: raw samples per mode that the run measured."""

    path: Path
    meta: dict[str, object]
    raws: dict[str, np.ndarray]  # mode -> array (n, 3): size_bytes, seq, time_ns

    @property
    def client(self) -> str:
        return str(self.meta["client_host"])

    @property
    def label(self) -> str:
        return str(self.meta["label"])

    @property
    def raw(self) -> np.ndarray:
        """Echo samples (the original benchmark mode)."""
        return self.raws["echo"]

    def sizes(self, mode: str = "echo") -> np.ndarray:
        return np.unique(self.raws[mode][:, 0]).astype(np.int64)


def load_run(path: Path) -> Run | None:
    """Load a run folder, or return None if it is incomplete (e.g. a failed start)."""
    if not all((path / f).exists() for f in REQUIRED_FILES):
        return None
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    raws = {
        mode: np.loadtxt(path / name, delimiter=",", skiprows=1, dtype=np.float64, ndmin=2)
        for mode, name in RAW_FILES.items()
        if (path / name).exists()
    }
    return Run(path=path, meta=meta, raws=raws) if raws else None


def find_runs(root: Path) -> list[Run]:
    """All complete runs directly under ``root``, oldest first (folder names start with a date)."""
    runs = (load_run(p) for p in sorted(root.iterdir()) if p.is_dir())
    return [r for r in runs if r is not None]


def latest_full_runs(runs: list[Run], mode: str = "echo") -> dict[tuple[str, str], Run]:
    """For each (client, label) pair, the most recent run with the most sizes in ``mode``.

    Only runs that measured ``mode`` count. This skips ``--quick`` checks (3 sizes) in
    favour of full sweeps, and re-runs win over older runs of the same pair.
    """
    best: dict[tuple[str, str], Run] = {}
    for run in runs:  # oldest first, so later runs replace earlier ones on ties
        if mode not in run.raws:
            continue
        key = (run.client, run.label)
        if key not in best or len(run.sizes(mode)) >= len(best[key].sizes(mode)):
            best[key] = run
    return best


# --------------------------------------------------------------------------- statistics
@dataclass
class SizeStats:
    """Per-size round-trip statistics computed from the raw samples (milliseconds)."""

    size_bytes: np.ndarray
    median_ms: np.ndarray
    p5_ms: np.ndarray
    p95_ms: np.ndarray
    count: np.ndarray
    crossings: int = 2  # payload crossings per call: 2 for echo, 1 for upload/download

    @property
    def throughput_mbit_s(self) -> np.ndarray:
        """Goodput: payload bits x network crossings, over the median call time."""
        return self.crossings * self.size_bytes * 8 / (self.median_ms / 1000) / 1e6


def size_stats(raw: np.ndarray, crossings: int = 2) -> SizeStats:
    sizes = np.unique(raw[:, 0])
    groups = [raw[raw[:, 0] == s, 2] / 1e6 for s in sizes]
    return SizeStats(
        size_bytes=sizes.astype(np.int64),
        median_ms=np.array([np.median(g) for g in groups]),
        p5_ms=np.array([np.percentile(g, 5) for g in groups]),
        p95_ms=np.array([np.percentile(g, 95) for g in groups]),
        count=np.array([g.size for g in groups]),
        crossings=crossings,
    )


# --------------------------------------------------------------------------- baseline
@dataclass
class Baseline:
    """Raw-network reference from experiments/01_communication/baseline/baseline_summary.csv.

    Keys use the baseline's node names (e.g. ``h3``, ``n2l``).
    """

    ping_ms: dict[frozenset[str], float]  # unordered pair -> RTT
    iperf_mbit_s: dict[tuple[str, str], float]  # (sender, receiver) -> TCP rate

    def floor_ms(self, size_bytes: np.ndarray, client: str, server: str) -> np.ndarray:
        """Raw-link floor of an echo from ``client`` to ``server``.

        ping RTT + payload at the client->server rate + payload at the server->client rate.
        """
        ping = self.ping_ms[frozenset((client, server))]
        up = self.iperf_mbit_s[(client, server)] * 1e6
        down = self.iperf_mbit_s[(server, client)] * 1e6
        bits = np.asarray(size_bytes, dtype=np.float64) * 8
        return ping + (bits / up + bits / down) * 1000


def load_baseline(path: Path) -> Baseline:
    ping: dict[frozenset[str], float] = {}
    iperf: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            link, median = row["link"], float(row["median"])
            if row["test"].startswith("ping"):
                a, b = (s.strip() for s in link.split("<->"))
                ping[frozenset((a, b))] = median
            elif row["test"].startswith("iperf"):
                a, b = (s.strip() for s in link.split("->"))
                iperf[(a, b)] = median
    return Baseline(ping_ms=ping, iperf_mbit_s=iperf)


# --------------------------------------------------------------------------- model
def fit_latency_bandwidth(
    size_bytes: np.ndarray, time_ms: np.ndarray, crossings: int = 2
) -> tuple[float, float]:
    """Fit ``time = alpha + (crossings * size * 8) / bandwidth`` to a sweep.

    ``crossings`` is how often the payload crosses the network per call: 2 for echo,
    1 for upload or download. Returns ``(alpha_ms, bandwidth_mbit_s)``.

    Least squares on *relative* error, so a 1 KB point (2 ms) counts as much as a
    50 MB point (3000 ms); a plain fit would let the big sizes decide everything and
    get alpha badly wrong.
    """
    bits = crossings * np.asarray(size_bytes, dtype=np.float64) * 8
    y = np.asarray(time_ms, dtype=np.float64) / 1000  # seconds
    design = np.column_stack([np.ones_like(bits), bits]) / y[:, None]
    (alpha_s, sec_per_bit), *_ = np.linalg.lstsq(design, np.ones_like(y), rcond=None)
    return float(alpha_s * 1000), float(1 / sec_per_bit / 1e6)


def predict_ms(
    size_bytes: np.ndarray, alpha_ms: float, bandwidth_mbit_s: float, crossings: int = 2
) -> np.ndarray:
    bits = crossings * np.asarray(size_bytes, dtype=np.float64) * 8
    return alpha_ms + bits / (bandwidth_mbit_s * 1e6) * 1000
