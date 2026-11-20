"""Phase 1 benchmark: gRPC call time and throughput across payload sizes.

Three modes (``modes`` in the config, or ``--modes``):
  echo      payload to the server and back   -> round-trip time
  upload    payload client -> server, tiny receipt back   (FL: client sends its update)
  download  tiny request, payload server -> client        (FL: client receives the model)

For each payload size the client:
  1. checks the full echoed content once (outside timing, echo mode),
  2. per mode: makes ``warmup`` untimed calls, then N timed calls. Each call is timed on
     this machine only (board clocks agree only to ~0.1-1 ms, so timestamps from two
     boards can't be subtracted),
  3. separately times protobuf encode/decode of the same message with no network.

Output, one folder per run under ``output_dir``:
  summary.csv        one row per (mode, size): median/p95/mean/std/min/max, throughput
  rtt_raw.csv        every timed echo call      (name kept for older runs)
  upload_raw.csv     every timed upload call
  download_raw.csv   every timed download call
  serialization.csv  protobuf encode/decode cost per size (this machine's CPU)
  meta.json          machine, versions and config, so the run can be reproduced

Start the server on the target first (python -m edge_fl.comms.server), then:
    python -m edge_fl.comms.benchmark --config experiments/01_communication/config.yaml \
        --target 192.168.50.1:50051 --label h3plus
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import platform
import socket
import time
from collections.abc import Callable
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Literal

import google.protobuf
import grpc
import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field

from edge_fl.comms.client import EchoClient
from edge_fl.comms.options import DEFAULT_MAX_MESSAGE_MB, MB
from edge_fl.comms.protos import echo_pb2

KB = 1024

Mode = Literal["echo", "upload", "download"]
MODES: tuple[Mode, ...] = ("echo", "upload", "download")
RAW_FILES: dict[Mode, str] = {
    "echo": "rtt_raw.csv",
    "upload": "upload_raw.csv",
    "download": "download_raw.csv",
}
# How many times the payload crosses the network in one call (for throughput).
CROSSINGS: dict[Mode, int] = {"echo": 2, "upload": 1, "download": 1}


# --------------------------------------------------------------------------- config
class BenchmarkConfig(BaseModel):
    """Benchmark settings, validated when loaded (wrong types or unknown keys are errors)."""

    model_config = ConfigDict(extra="forbid")

    target: str = "127.0.0.1:50051"
    max_message_mb: int = Field(DEFAULT_MAX_MESSAGE_MB, ge=1)
    modes: list[Mode] = Field(default_factory=lambda: list(MODES), min_length=1)
    payload_sizes_kb: list[int] = Field(
        default_factory=lambda: [1, 4, 16, 64, 256, 1024, 4096, 16384, 51200], min_length=1
    )
    warmup: int = Field(20, ge=0)
    repeats_min: int = Field(10, ge=1)
    repeats_max: int = Field(500, ge=1)
    bytes_budget_mb: int = Field(500, ge=1)
    connect_timeout_s: float = Field(10.0, gt=0)  # give up if the server isn't up by then
    output_dir: str = "results/01_communication"


def load_config(path: str | Path | None) -> BenchmarkConfig:
    if path is None:
        return BenchmarkConfig()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return BenchmarkConfig(**data)


def repeats_for(size_bytes: int, cfg: BenchmarkConfig) -> int:
    """Timed calls for one size: a fixed data budget, clamped to [repeats_min, repeats_max].

    Small payloads get many repeats (cheap, and their timings are noisier); large ones get
    few, so a 50 MB step doesn't take an hour on a 300 Mbit/s link.
    """
    by_budget = (cfg.bytes_budget_mb * MB) // max(size_bytes, 1)
    return int(max(cfg.repeats_min, min(cfg.repeats_max, by_budget)))


# --------------------------------------------------------------------------- measuring
# One "call" function per mode: (seq) -> reply, plus a "check" that the reply is right.
Call = Callable[[int], object]
Check = Callable[[object, int], bool]


def mode_call(client: EchoClient, mode: Mode, data: bytes) -> tuple[Call, Check]:
    """The gRPC call to time for ``mode``, and a cheap check of its reply.

    The checks only compare lengths and sequence numbers (cheap); the full byte-for-byte
    comparison is done once per size, outside timing.
    """
    size = len(data)
    if mode == "echo":
        return (
            lambda seq: client.echo(data, seq=seq),
            lambda r, seq: r.seq == seq and len(r.data) == size,  # type: ignore[attr-defined]
        )
    if mode == "upload":
        return (
            lambda seq: client.upload(data, seq=seq),
            lambda r, seq: r.seq == seq and r.received_bytes == size,  # type: ignore[attr-defined]
        )
    return (
        lambda seq: client.download(size, seq=seq),
        lambda r, seq: r.seq == seq and len(r.data) == size,  # type: ignore[attr-defined]
    )


def time_calls(call: Call, check: Check, n: int, seq_start: int) -> list[int]:
    """Make ``n`` calls and return each call's duration in nanoseconds.

    Only the call itself is inside the timer; the reply check comes after it.
    """
    samples: list[int] = []
    for i in range(n):
        seq = seq_start + i
        t0 = time.perf_counter_ns()
        reply = call(seq)
        t1 = time.perf_counter_ns()
        if not check(reply, seq):
            raise RuntimeError(f"bad reply for seq {seq} (wrong sequence number or length)")
        samples.append(t1 - t0)
    return samples


def time_serialization(data: bytes, n: int) -> tuple[list[int], list[int]]:
    """Time protobuf encode (object -> bytes) and decode (bytes -> object), no network.

    This is CPU work done on both ends of every real call, so it shows how much of the
    round trip is computation rather than transfer (expected to matter more on arm64).
    """
    message = echo_pb2.Payload(data=data, seq=1)
    encode_ns: list[int] = []
    decode_ns: list[int] = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        raw = message.SerializeToString()
        t1 = time.perf_counter_ns()
        echo_pb2.Payload.FromString(raw)
        t2 = time.perf_counter_ns()
        encode_ns.append(t1 - t0)
        decode_ns.append(t2 - t1)
    return encode_ns, decode_ns


def summarize_ns(samples_ns: list[int]) -> dict[str, float]:
    """Median, p95, mean, std, min, max in milliseconds."""
    ms = np.asarray(samples_ns, dtype=np.float64) / 1e6
    return {
        "median_ms": float(np.median(ms)),
        "p95_ms": float(np.percentile(ms, 95)),
        "mean_ms": float(ms.mean()),
        "std_ms": float(ms.std(ddof=1)) if ms.size > 1 else 0.0,
        "min_ms": float(ms.min()),
        "max_ms": float(ms.max()),
    }


def throughput_mbit_s(size_bytes: int, time_ms: float, crossings: int = 2) -> float:
    """Goodput of one call: payload bits x times it crosses the network, over the time.

    Echo crosses twice (there and back); upload and download cross once.
    """
    return (crossings * size_bytes * 8) / (time_ms / 1000) / 1e6


# --------------------------------------------------------------------------- running
def run_metadata(cfg: BenchmarkConfig, label: str) -> dict[str, object]:
    return {
        "client_host": socket.gethostname(),
        "target": cfg.target,
        "label": label,
        "machine": platform.machine(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "grpcio": grpc.__version__,
        "protobuf": google.protobuf.__version__,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        "config": cfg.model_dump(),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(cfg: BenchmarkConfig, label: str) -> Path:
    """Run the full sweep against ``cfg.target`` and return the run folder."""
    meta = run_metadata(cfg, label)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = Path(cfg.output_dir) / f"{stamp}_{meta['client_host']}_to_{label}"

    print(f"benchmark ({', '.join(cfg.modes)}): {meta['client_host']} -> {cfg.target} ({label})")
    # Connect *before* creating the run folder: if the server isn't reachable,
    # EchoClient raises here and no empty folder is left behind.
    with EchoClient(cfg.target, cfg.max_message_mb, cfg.connect_timeout_s) as client:
        run_dir.mkdir(parents=True, exist_ok=True)
        summary_rows, serial_rows = sweep(cfg, client, run_dir)

    meta["finished"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_csv(run_dir / "summary.csv", summary_rows)
    write_csv(run_dir / "serialization.csv", serial_rows)
    print(f"saved {run_dir}")
    return run_dir


def sweep(
    cfg: BenchmarkConfig, client: EchoClient, run_dir: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Measure every payload size in every mode.

    Writes each timed call to that mode's raw file; returns the summary rows
    (one per mode and size) and the serialization rows (one per size).
    """
    summary_rows: list[dict[str, object]] = []
    serial_rows: list[dict[str, object]] = []
    seq = 1

    with ExitStack() as stack:  # one open raw file per mode, all closed at the end
        raw = {}
        for mode in cfg.modes:
            fh = stack.enter_context(
                (run_dir / RAW_FILES[mode]).open("w", newline="", encoding="utf-8")
            )
            raw[mode] = csv.writer(fh, lineterminator="\n")
            raw[mode].writerow(["size_bytes", "seq", "rtt_ns"])

        for size_kb in cfg.payload_sizes_kb:
            size = size_kb * KB
            data = os.urandom(size)  # random: incompressible, unlike zeros

            # 1) correctness, untimed: the full payload must come back byte for byte
            if client.echo(data, seq=0).data != data:
                raise RuntimeError(f"echoed content differs at {size_kb} KB")

            n = repeats_for(size, cfg)
            for mode in cfg.modes:
                call, check = mode_call(client, mode, data)

                # 2) warm-up, discarded (also fills the server's download cache)
                time_calls(call, check, cfg.warmup, seq_start=seq)
                seq += cfg.warmup

                # 3) timed calls, with the garbage collector paused so it can't inject
                #    pauses that have nothing to do with the network
                gc.collect()
                gc.disable()
                try:
                    samples = time_calls(call, check, n, seq_start=seq)
                finally:
                    gc.enable()
                raw[mode].writerows([size, seq + i, s] for i, s in enumerate(samples))
                seq += n

                stats = summarize_ns(samples)
                mbit = throughput_mbit_s(size, stats["median_ms"], CROSSINGS[mode])
                summary_rows.append(
                    {
                        "mode": mode,
                        "size_bytes": size,
                        "size_kb": size_kb,
                        "repeats": n,
                        **stats,
                        "throughput_mbit_s": mbit,
                    }
                )
                print(
                    f"  {mode:<8} {size_kb:>6} KB  n={n:<4} median {stats['median_ms']:9.3f} ms"
                    f"  p95 {stats['p95_ms']:9.3f} ms  {mbit:8.1f} Mbit/s"
                )

            # 4) serialization only, on this machine (independent of mode)
            encode_ns, decode_ns = time_serialization(data, n)
            serial_rows.append(
                {
                    "size_bytes": size,
                    "size_kb": size_kb,
                    "repeats": n,
                    "encode_median_ms": summarize_ns(encode_ns)["median_ms"],
                    "decode_median_ms": summarize_ns(decode_ns)["median_ms"],
                }
            )
    return summary_rows, serial_rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="gRPC benchmark (Phase 1).")
    parser.add_argument("--config", default=None, help="YAML config (see experiments/01_...)")
    parser.add_argument("--target", default=None, help="host:port of the server")
    parser.add_argument("--label", default=None, help="name for the server side in the run folder")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--modes", nargs="+", choices=MODES, default=None, help="which calls to measure"
    )
    parser.add_argument(
        "--quick", action="store_true", help="tiny sweep to check the setup (seconds, not minutes)"
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    overrides: dict[str, object] = {}
    if args.target:
        overrides["target"] = args.target
    if args.output_dir:
        overrides["output_dir"] = args.output_dir
    if args.modes:
        overrides["modes"] = args.modes
    if args.quick:
        overrides |= {"payload_sizes_kb": [1, 64, 1024], "warmup": 3, "repeats_max": 20}
    cfg = BenchmarkConfig(**(cfg.model_dump() | overrides))  # re-validates the overrides

    label = args.label or cfg.target.rsplit(":", 1)[0]
    run(cfg, label)


if __name__ == "__main__":
    main()
