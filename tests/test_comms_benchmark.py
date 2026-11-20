"""Benchmark logic: repeat counts, statistics, and a tiny end-to-end run on loopback."""

import csv
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from edge_fl.comms.benchmark import (
    BenchmarkConfig,
    load_config,
    repeats_for,
    run,
    summarize_ns,
    throughput_mbit_s,
)
from edge_fl.comms.options import MB
from edge_fl.comms.server import start_server

REPO = Path(__file__).resolve().parents[1]


def test_repeats_scale_with_size_and_are_clamped() -> None:
    cfg = BenchmarkConfig(repeats_min=10, repeats_max=500, bytes_budget_mb=500)
    assert repeats_for(1024, cfg) == 500  # budget allows far more -> capped at max
    assert repeats_for(16 * MB, cfg) == 31  # 500 MB / 16 MB
    assert repeats_for(50 * MB, cfg) == 10  # budget allows 10 -> exactly min


def test_summary_statistics() -> None:
    stats = summarize_ns([1_000_000, 2_000_000, 3_000_000])  # 1, 2, 3 ms
    assert stats["median_ms"] == 2.0
    assert stats["min_ms"] == 1.0 and stats["max_ms"] == 3.0
    assert stats["std_ms"] == pytest.approx(1.0)


def test_throughput_counts_both_directions() -> None:
    # 1 MB each way in 80 ms -> 2 * 8_388_608 bits / 0.08 s = 209.7 Mbit/s
    assert throughput_mbit_s(MB, 80.0) == pytest.approx(209.7152)


def test_repo_config_is_valid() -> None:
    cfg = load_config(REPO / "experiments" / "01_communication" / "config.yaml")
    assert max(cfg.payload_sizes_kb) * 1024 <= cfg.max_message_mb * MB


def test_unknown_config_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BenchmarkConfig(repeat_max=5)  # type: ignore[call-arg]  # typo of repeats_max


@pytest.fixture
def server_target() -> Iterator[str]:
    server, port = start_server(host="127.0.0.1", port=0)
    yield f"127.0.0.1:{port}"
    server.stop(grace=None)


def test_end_to_end_run_writes_all_outputs(server_target: str, tmp_path: Path) -> None:
    cfg = BenchmarkConfig(
        target=server_target,
        payload_sizes_kb=[1, 64],
        warmup=2,
        repeats_min=3,
        repeats_max=5,
        output_dir=str(tmp_path),
    )
    run_dir = run(cfg, label="loopback")

    with (run_dir / "summary.csv").open(encoding="utf-8") as fh:
        summary = list(csv.DictReader(fh))
    assert [int(r["size_kb"]) for r in summary] == [1, 64]
    assert all(float(r["median_ms"]) > 0 for r in summary)

    with (run_dir / "rtt_raw.csv").open(encoding="utf-8") as fh:
        assert sum(1 for _ in fh) == 1 + 5 + 5  # header + 5 samples per size

    assert (run_dir / "serialization.csv").exists()
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["label"] == "loopback" and meta["config"]["warmup"] == 2
