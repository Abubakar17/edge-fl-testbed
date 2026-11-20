"""Analysis maths: model fit, raw-link floor, baseline parsing and run selection."""

import json
from pathlib import Path

import numpy as np
import pytest

from edge_fl.comms.analysis import (
    Baseline,
    find_runs,
    fit_latency_bandwidth,
    latest_full_runs,
    load_baseline,
    predict_ms,
    size_stats,
)

REPO = Path(__file__).resolve().parents[1]
BASELINE = REPO / "experiments" / "01_communication" / "baseline" / "baseline_summary.csv"


def test_fit_recovers_known_model() -> None:
    sizes = np.array([1, 64, 1024, 16384, 51200]) * 1024
    true = predict_ms(sizes, alpha_ms=2.0, bandwidth_mbit_s=300.0)
    alpha, bw = fit_latency_bandwidth(sizes, true)
    assert alpha == pytest.approx(2.0, rel=1e-6)
    assert bw == pytest.approx(300.0, rel=1e-6)


def test_floor_is_ping_plus_transfer_both_ways() -> None:
    base = Baseline(
        ping_ms={frozenset(("a", "b")): 0.5},
        iperf_mbit_s={("a", "b"): 100.0, ("b", "a"): 200.0},
    )
    # 1 MB = 8_388_608 bits: 83.886 ms at 100 Mbit/s + 41.943 ms at 200 Mbit/s + 0.5 ms
    assert base.floor_ms(np.array([1024 * 1024]), "a", "b")[0] == pytest.approx(126.3289, 1e-4)


def test_real_baseline_parses() -> None:
    base = load_baseline(BASELINE)
    assert base.ping_ms[frozenset(("h3", "n2l"))] == pytest.approx(0.483)
    assert base.iperf_mbit_s[("n2l", "h3")] == pytest.approx(293.9)


def test_size_stats_groups_by_size() -> None:
    raw = np.array([[1024, 1, 1e6], [1024, 2, 3e6], [2048, 3, 2e6]])  # rtt in ns
    st = size_stats(raw)
    assert st.size_bytes.tolist() == [1024, 2048]
    assert st.median_ms.tolist() == [2.0, 2.0]
    assert st.count.tolist() == [2, 1]


def _fake_run(root: Path, name: str, client: str, label: str, sizes: list[int]) -> None:
    d = root / name
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"client_host": client, "label": label}))
    (d / "summary.csv").write_text("size_bytes\n")
    lines = ["size_bytes,seq,rtt_ns"] + [f"{s},1,1000000" for s in sizes]
    (d / "rtt_raw.csv").write_text("\n".join(lines) + "\n")


def test_selection_prefers_full_sweep_and_skips_empty(tmp_path: Path) -> None:
    _fake_run(tmp_path, "2026-01-01_100000_n2l-1_to_h3plus", "n2l-1", "h3plus", [1, 2, 3, 4])
    _fake_run(tmp_path, "2026-01-01_110000_n2l-1_to_h3plus", "n2l-1", "h3plus", [1, 2])  # quick
    (tmp_path / "2026-01-01_120000_n2l-1_to_h3plus").mkdir()  # failed start, empty
    best = latest_full_runs(find_runs(tmp_path))
    assert list(best) == [("n2l-1", "h3plus")]
    assert best[("n2l-1", "h3plus")].path.name.startswith("2026-01-01_100000")
