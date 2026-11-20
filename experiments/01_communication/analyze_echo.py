#!/usr/bin/env python3
"""Phase 1 analysis: figures and summary tables from the echo benchmark runs.

Usage (from the repo root, after collecting the run folders with scp):
    uv run python experiments/01_communication/analyze_echo.py
    uv run python experiments/01_communication/analyze_echo.py --runs <dir> <dir> ...

By default, picks the latest *full* run for each (client, server) pair under
results/01_communication/ (quick checks and failed starts are skipped) and compares it
with the raw-network baseline in experiments/01_communication/baseline/.

Writes to results/01_communication/analysis/:
    fig1_rtt_vs_size.png        round-trip time per payload size, with the raw-link floor
    fig2_throughput.png         echo throughput per payload size, with the iperf3 reference
    fig3_time_breakdown.png     share of each round trip that is network vs software
    fig4_model_fit.png          fitted latency-bandwidth model for the board-to-board runs
    fig5_upload_download.png    one-way throughput per direction (needs upload/download runs)
    phase1_summary.md / .csv    the numbers behind the figures
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import matplotlib

matplotlib.use("Agg")  # file output only, no window
import matplotlib.pyplot as plt
import numpy as np

from edge_fl.comms.analysis import (
    Baseline,
    Run,
    SizeStats,
    find_runs,
    fit_latency_bandwidth,
    latest_full_runs,
    load_baseline,
    load_run,
    predict_ms,
    size_stats,
)

HERE = Path(__file__).resolve().parent

# Map hostnames (meta.json) and --label values to the node names used in the baseline.
# Add an entry per new board.
NODE = {"odroid-H3": "h3", "h3plus": "h3", "h3": "h3", "n2l-1": "n2l", "n2l": "n2l"}
DISPLAY = {"h3": "H3+", "n2l": "N2L"}

# Fixed scenario order = fixed colour + marker per scenario in every figure.
ORDER = [("h3", "h3"), ("n2l", "n2l"), ("n2l", "h3"), ("h3", "n2l")]
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

SURFACE, INK, INK_2, GRID, FLOOR = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0", "#52514e"

# Upload/download figure: colour = which way the data physically flows (sender, receiver).
# Palette slots 7 and 8, so they never look like the four scenario colours above.
FLOW_COLORS = {("n2l", "h3"): "#e34948", ("h3", "n2l"): "#6250d6"}


class Labeled(Protocol):
    """Anything that can be drawn as a labelled line."""

    name: str
    color: str
    stats: SizeStats


@dataclass
class Scenario:
    client: str  # baseline node name
    server: str
    run_dir: Path
    stats: SizeStats
    color: str
    marker: str

    @property
    def loopback(self) -> bool:
        return self.client == self.server

    @property
    def name(self) -> str:
        if self.loopback:
            return f"{DISPLAY.get(self.client, self.client)} loopback"
        return f"{DISPLAY.get(self.client, self.client)} → {DISPLAY.get(self.server, self.server)}"


@dataclass
class OneWay:
    """One-way measurement: who sent the data, who received it, and who ran the client."""

    sender: str
    receiver: str
    client: str
    mode: str  # "upload" (client sends) or "download" (client receives)
    run_dir: Path
    stats: SizeStats

    @property
    def name(self) -> str:
        verb = "uploads" if self.mode == "upload" else "downloads"
        flow = (
            f"{DISPLAY.get(self.sender, self.sender)} → {DISPLAY.get(self.receiver, self.receiver)}"
        )
        return f"{flow} ({DISPLAY.get(self.client, self.client)} {verb})"

    @property
    def color(self) -> str:
        return FLOW_COLORS.get((self.sender, self.receiver), FLOOR)


# --------------------------------------------------------------------------- data
def select_runs(run_dirs: list[Path] | None, root: Path, mode: str) -> dict[tuple[str, str], Run]:
    """Runs to use for ``mode``, keyed by (client, server) node names."""
    if run_dirs:
        loaded = [load_run(d) for d in run_dirs]
        runs = {(r.client, r.label): r for r in loaded if r is not None and mode in r.raws}
    else:
        runs = latest_full_runs(find_runs(root), mode)
    return {(NODE.get(c, c), NODE.get(lbl, lbl)): r for (c, lbl), r in runs.items()}


def build_oneway(run_dirs: list[Path] | None, root: Path) -> list[OneWay]:
    """Board-to-board upload/download measurements, ordered by data-flow direction."""
    out = []
    for mode in ("upload", "download"):
        for (client, server), run in select_runs(run_dirs, root, mode).items():
            if client == server:
                continue  # loopback: no direction to speak of
            sender, receiver = (client, server) if mode == "upload" else (server, client)
            stats = size_stats(run.raws[mode], crossings=1)
            out.append(OneWay(sender, receiver, client, mode, run.path, stats))
    return sorted(out, key=lambda o: (o.sender, o.mode))


def build_scenarios(run_dirs: list[Path] | None, root: Path) -> list[Scenario]:
    by_pair = select_runs(run_dirs, root, "echo")
    pairs = [p for p in ORDER if p in by_pair] + sorted(p for p in by_pair if p not in ORDER)
    return [
        Scenario(
            c,
            s,
            by_pair[(c, s)].path,
            size_stats(by_pair[(c, s)].raw),
            COLORS[i % len(COLORS)],
            MARKERS[i % len(MARKERS)],
        )
        for i, (c, s) in enumerate(pairs)
    ]


def size_label(size_bytes: float) -> str:
    kb = size_bytes / 1024
    return f"{kb / 1024:g} MB" if kb >= 1024 else f"{kb:g} KB"


# --------------------------------------------------------------------------- style
def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": "#c3c2b7",
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.titlesize": 12,
            "axes.titlelocation": "left",
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "text.color": INK,
            "font.size": 10,
            "legend.frameon": False,
            "lines.linewidth": 2,
            "lines.markersize": 6,
        }
    )


def size_axis(ax: plt.Axes, sizes: np.ndarray) -> None:
    ax.set_xscale("log", base=2)
    ax.set_xticks(sizes, [size_label(s) for s in sizes], rotation=0)
    ax.minorticks_off()
    ax.set_xlabel("Payload size")


def label_line_ends(
    ax: plt.Axes,
    scen: Sequence[Labeled],
    values: list[np.ndarray],
    side: str = "left",
    min_gap_frac: float = 0.05,
) -> None:
    """Direct label at one end of each line (log y), nudged apart so labels never overlap.

    The minimum gap is a fraction of the axis height, so it works whatever the y-range.
    """
    idx = 0 if side == "left" else -1
    xs = [float(sc.stats.size_bytes[idx]) for sc in scen]
    ys = [float(v[idx]) for v in values]
    lo, hi = (np.log10(v) for v in ax.get_ylim())
    gap = min_gap_frac * (hi - lo)
    placed: list[float] = []
    for i in np.argsort(ys):
        y = np.log10(ys[i])
        if placed and y - placed[-1] < gap:
            y = placed[-1] + gap
        placed.append(y)
        ax.annotate(
            scen[i].name,
            (xs[i], ys[i]),
            xytext=(xs[i] / 1.3 if side == "left" else xs[i] * 1.3, 10**y),
            ha="right" if side == "left" else "left",
            va="center",
            fontsize=9,
            color=INK,
            bbox={"fc": SURFACE, "ec": "none", "pad": 1.5},  # mask lines behind the text
            arrowprops={"arrowstyle": "-", "color": scen[i].color, "lw": 1},
        )


# --------------------------------------------------------------------------- figures
def fig_rtt(scen: list[Scenario], base: Baseline | None, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for sc in scen:
        st = sc.stats
        ax.fill_between(st.size_bytes, st.p5_ms, st.p95_ms, color=sc.color, alpha=0.15, lw=0)
        ax.plot(
            st.size_bytes,
            st.median_ms,
            marker=sc.marker,
            color=sc.color,
            label=sc.name,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
        )
    cross = [sc for sc in scen if not sc.loopback]
    if base and cross:
        sizes = cross[0].stats.size_bytes
        ax.plot(
            sizes,
            base.floor_ms(sizes, cross[0].client, cross[0].server),
            ls="--",
            color=FLOOR,
            lw=1.5,
            label="Raw-link floor H3+ ↔ N2L (ping + iperf3)",
        )
    size_axis(ax, scen[0].stats.size_bytes)
    ax.set_yscale("log")
    ax.set_ylabel("Round-trip time (ms, log scale)")
    ax.set_title("gRPC echo round-trip time (median, band = p5–p95)")
    ax.set_xlim(scen[0].stats.size_bytes[0] / 10, None)  # room for the direct labels
    label_line_ends(ax, scen, [sc.stats.median_ms for sc in scen], side="left")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def fig_throughput(scen: list[Scenario], base: Baseline | None, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for sc in scen:
        ax.plot(
            sc.stats.size_bytes,
            sc.stats.throughput_mbit_s,
            marker=sc.marker,
            color=sc.color,
            label=sc.name,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
        )
    if base and ("h3", "n2l") in base.iperf_mbit_s and ("n2l", "h3") in base.iperf_mbit_s:
        up, down = base.iperf_mbit_s[("n2l", "h3")], base.iperf_mbit_s[("h3", "n2l")]
        ref = 2 / (1 / up + 1 / down)  # echo = up then down: harmonic mean of the two rates
        ax.axhline(
            ref,
            ls="--",
            color=FLOOR,
            lw=1.5,
            label=f"Raw TCP H3+ ↔ N2L, echo-equivalent ({ref:.0f} Mbit/s, iperf3)",
        )
    size_axis(ax, scen[0].stats.size_bytes)
    ax.set_yscale("log")
    ax.set_ylabel("Throughput (Mbit/s, log scale)")
    ax.set_title("gRPC echo throughput (2 × payload ÷ median RTT)")
    ax.set_xlim(None, scen[0].stats.size_bytes[-1] * 12)  # room for the direct labels
    label_line_ends(ax, scen, [sc.stats.throughput_mbit_s for sc in scen], side="right")
    ax.legend(loc="lower right")  # the empty corner: no line runs through it
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def fig_breakdown(scen: list[Scenario], base: Baseline, out: Path) -> None:
    cross = [sc for sc in scen if not sc.loopback]
    fig, axes = plt.subplots(
        1, len(cross), figsize=(6.5 * len(cross), 4.8), sharey=True, squeeze=False
    )
    for ax, sc in zip(axes[0], cross, strict=True):
        st = sc.stats
        floor = np.minimum(base.floor_ms(st.size_bytes, sc.client, sc.server), st.median_ms)
        net = 100 * floor / st.median_ms
        x = np.arange(st.size_bytes.size)
        ax.bar(x, net, color="#3d3c39", edgecolor=SURFACE, lw=2, label="Raw network (floor)")
        ax.bar(
            x,
            100 - net,
            bottom=net,
            color="#b9b7ad",
            edgecolor=SURFACE,
            lw=2,
            label="gRPC + protobuf + Python + CPU",
        )
        for xi, v in zip(x, net, strict=True):  # small enough to stay inside the bar
            ax.text(xi, v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=7, color=SURFACE)
        ax.set_xticks(x, [size_label(s) for s in st.size_bytes], rotation=45, ha="right")
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
        ax.set_title(sc.name)
        ax.set_xlabel("Payload size")
    axes[0][0].set_ylabel("Share of median round-trip time (%)")
    axes[0][-1].legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.suptitle("Where the round-trip time goes", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def fig_model(scen: list[Scenario], fits: dict[str, tuple[float, float]], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for sc in scen:
        if sc.loopback:
            continue
        alpha, bw = fits[sc.name]
        st = sc.stats
        ax.plot(
            st.size_bytes,
            st.median_ms,
            ls="none",
            marker=sc.marker,
            color=sc.color,
            ms=8,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=f"{sc.name} measured",
        )
        dense = np.geomspace(st.size_bytes[0], st.size_bytes[-1], 200)
        ax.plot(
            dense,
            predict_ms(dense, alpha, bw),
            color=sc.color,
            lw=1.5,
            ls="--",
            label=f"{sc.name} model: {alpha:.2f} ms + 2·size / {bw:.0f} Mbit/s",
        )
    size_axis(ax, scen[0].stats.size_bytes)
    ax.set_yscale("log")
    ax.set_ylabel("Round-trip time (ms, log scale)")
    ax.set_title("Latency–bandwidth model: time = α + data / bandwidth")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def fig_oneway(oneway: list[OneWay], base: Baseline | None, out: Path) -> None:
    """One-way throughput. Colour = direction the data flows; solid = the sender ran the
    client (upload), dashed = the receiver ran the client (download). Two lines of the
    same colour measure the same direction with the client role swapped, so they should
    agree; the dotted line is iperf3's raw TCP rate for that direction."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for ow in oneway:
        upload = ow.mode == "upload"
        ax.plot(
            ow.stats.size_bytes,
            ow.stats.throughput_mbit_s,
            color=ow.color,
            ls="-" if upload else "--",
            marker="o" if upload else "s",
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=ow.name,
        )
    if base:
        for (sender, receiver), color in FLOW_COLORS.items():
            rate = base.iperf_mbit_s.get((sender, receiver))
            if rate:
                flow = f"{DISPLAY[sender]} → {DISPLAY[receiver]}"
                ax.axhline(rate, color=color, ls=":", lw=1.5, label=f"iperf3 {flow} ({rate:.0f})")
    size_axis(ax, oneway[0].stats.size_bytes)
    ax.set_yscale("log")
    ax.set_ylabel("Throughput (Mbit/s, log scale)")
    ax.set_title("One-way throughput: upload vs download (payload ÷ median time)")
    top = max(float(ow.stats.throughput_mbit_s.max()) for ow in oneway)
    ax.set_ylim(None, top * 2.5)  # headroom so lines, iperf3 lines and labels don't crowd
    ax.set_xlim(None, oneway[0].stats.size_bytes[-1] * 8)  # room for the direct labels
    # Same-colour lines measure the same direction and should overlap, so label each
    # *direction* once (on its upload line); the legend explains solid vs dashed.
    flows = {(ow.sender, ow.receiver): ow for ow in oneway if ow.mode == "upload"}
    labels = [
        Scenario(s, r, ow.run_dir, ow.stats, ow.color, "o") for (s, r), ow in flows.items()
    ]  # Scenario's name is "A → B", exactly the direction label wanted here
    label_line_ends(ax, labels, [lb.stats.throughput_mbit_s for lb in labels], side="right")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------- tables
def oneway_markdown(
    oneway: list[OneWay], fits1: dict[str, tuple[float, float]], base: Baseline | None
) -> list[str]:
    """Markdown section for the upload/download measurements."""
    md = [
        "",
        "## One-way: upload and download",
        "",
        "Median time in ms (throughput in Mbit/s). Name = data flow (who ran the client).",
        "",
        "| Size | " + " | ".join(ow.name for ow in oneway) + " |",
        "|---" * (len(oneway) + 1) + "|",
    ]
    for i, size in enumerate(oneway[0].stats.size_bytes):
        cells = [
            f"{ow.stats.median_ms[i]:.3f} ({ow.stats.throughput_mbit_s[i]:.0f})" for ow in oneway
        ]
        md.append(f"| {size_label(size)} | " + " | ".join(cells) + " |")
    md += [
        "",
        "One-way model, `time = α + size / bandwidth`, against iperf3 for the same direction:",
        "",
        "| Measurement | α (ms) | Bandwidth (Mbit/s) | iperf3 (Mbit/s) | gRPC / iperf3 |",
        "|---|---|---|---|---|",
    ]
    for ow in oneway:
        alpha, bw = fits1[ow.name]
        ref = base.iperf_mbit_s.get((ow.sender, ow.receiver)) if base else None
        ratio = f"{100 * bw / ref:.0f}%" if ref else "-"
        md.append(f"| {ow.name} | {alpha:.2f} | {bw:.1f} | {ref or '-'} | {ratio} |")
    md += ["", "Runs used:", ""] + [f"- {ow.name}: `{ow.run_dir.name}`" for ow in oneway]
    return md


def write_tables(
    scen: list[Scenario],
    base: Baseline | None,
    fits: dict[str, tuple[float, float]],
    out_dir: Path,
    oneway: list[OneWay] | None = None,
    fits1: dict[str, tuple[float, float]] | None = None,
) -> None:
    rows = []
    for sc in scen:
        st = sc.stats
        floor = (
            base.floor_ms(st.size_bytes, sc.client, sc.server)
            if base and not sc.loopback
            else np.full(st.size_bytes.size, np.nan)
        )
        for i, size in enumerate(st.size_bytes):
            rows.append(
                {
                    "scenario": sc.name,
                    "size": size_label(size),
                    "size_bytes": int(size),
                    "n": int(st.count[i]),
                    "median_ms": st.median_ms[i],
                    "p5_ms": st.p5_ms[i],
                    "p95_ms": st.p95_ms[i],
                    "throughput_mbit_s": st.throughput_mbit_s[i],
                    "floor_ms": floor[i],
                    "network_share_pct": 100 * floor[i] / st.median_ms[i],
                }
            )
    with (out_dir / "phase1_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    md = [
        "# Phase 1: gRPC echo benchmark summary",
        "",
        "Median round-trip time in ms (throughput in Mbit/s).",
        "",
    ]
    md.append("| Size | " + " | ".join(sc.name for sc in scen) + " |")
    md.append("|---" * (len(scen) + 1) + "|")
    for i, size in enumerate(scen[0].stats.size_bytes):
        cells = [
            f"{sc.stats.median_ms[i]:.3f} ({sc.stats.throughput_mbit_s[i]:.0f})" for sc in scen
        ]
        md.append(f"| {size_label(size)} | " + " | ".join(cells) + " |")
    if fits:
        md += [
            "",
            "Latency–bandwidth model, `time = α + 2·size / bandwidth`:",
            "",
            "| Scenario | α (ms) | Bandwidth (Mbit/s) |",
            "|---|---|---|",
        ]
        md += [f"| {name} | {a:.2f} | {bw:.1f} |" for name, (a, bw) in fits.items()]
    md += ["", "Runs used:", ""] + [f"- {sc.name}: `{sc.run_dir.name}`" for sc in scen]
    if oneway and fits1:
        md += oneway_markdown(oneway, fits1, base)
    (out_dir / "phase1_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Phase 1 figures and summary tables.")
    parser.add_argument("--results", type=Path, default=Path("results/01_communication"))
    parser.add_argument("--runs", type=Path, nargs="*", help="explicit run folders to use")
    parser.add_argument("--baseline", type=Path, default=HERE / "baseline" / "baseline_summary.csv")
    parser.add_argument("--out", type=Path, default=None, help="default: <results>/analysis")
    args = parser.parse_args(argv)
    # Scenario names contain "→"; the default Windows console encoding (cp1252) can't print it.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")

    scen = build_scenarios(args.runs, args.results)
    if not scen:
        raise SystemExit(f"no complete runs found under {args.results}")
    base = load_baseline(args.baseline) if args.baseline.exists() else None
    fits = {
        sc.name: fit_latency_bandwidth(sc.stats.size_bytes, sc.stats.median_ms)
        for sc in scen
        if not sc.loopback
    }
    out = args.out or args.results / "analysis"
    out.mkdir(parents=True, exist_ok=True)

    style()
    fig_rtt(scen, base, out / "fig1_rtt_vs_size.png")
    fig_throughput(scen, base, out / "fig2_throughput.png")
    if base and any(not sc.loopback for sc in scen):
        fig_breakdown(scen, base, out / "fig3_time_breakdown.png")
    if fits:
        fig_model(scen, fits, out / "fig4_model_fit.png")

    # Upload/download, if any runs measured them (older runs are echo only).
    oneway = build_oneway(args.runs, args.results)
    fits1 = {
        ow.name: fit_latency_bandwidth(ow.stats.size_bytes, ow.stats.median_ms, crossings=1)
        for ow in oneway
    }
    if oneway:
        fig_oneway(oneway, base, out / "fig5_upload_download.png")
    write_tables(scen, base, fits, out, oneway, fits1)

    for sc in scen:
        print(f"{sc.name:<16} {sc.run_dir.name}")
    for name, (a, bw) in fits.items():
        print(f"model {name}: alpha {a:.2f} ms, bandwidth {bw:.1f} Mbit/s")
    for name, (a, bw) in fits1.items():
        print(f"one-way {name}: alpha {a:.2f} ms, bandwidth {bw:.1f} Mbit/s")
    if not oneway:
        print("no upload/download runs yet: figure 5 skipped")
    print(f"saved figures and tables to {out}")


if __name__ == "__main__":
    main()
