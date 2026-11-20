# Phase 1: Communication

Make the standalone devices exchange messages over gRPC, then measure what that costs.

**Questions**
- Round-trip latency between nodes, and how it grows with payload size.
- How close gRPC gets to the raw link, measured with `iperf3` in [`baseline/`](baseline/).
- How much of each round trip is protobuf serialization (CPU) rather than transfer, on x86 and on arm64.
- Upload and download measured separately, since FL clients upload updates and download the model.

**Code:** `src/edge_fl/comms/`: the `protos/echo.proto` contract (`Echo`, `Upload` and `Download` calls), `server.py`, `client.py`, `benchmark.py` and `analysis.py`
**Config:** [`config.yaml`](config.yaml)
**Outputs:** `results/01_communication/<date>_<client>_to_<label>/`, containing:
- `summary.csv`
- one raw file per mode: `rtt_raw.csv` (echo), `upload_raw.csv`, `download_raw.csv`
- `serialization.csv`
- `meta.json`

## Baseline (raw network)

`baseline/` holds `ping` and `iperf3` for every pair of devices, plus `summarize_baseline.py`.
H3+ ↔ N2L: 0.48 ms RTT, 294 Mbit/s N2L → H3+, 335 Mbit/s H3+ → N2L.

## Running the benchmark

The server runs on one node and the benchmark on another. Each call is timed on the
client only, so clock differences between boards don't matter.

`--modes` chooses what to measure: `echo`, `upload` and `download`. All three run by default.

```bash
# On the server node (e.g. the H3+):
uv run python -m edge_fl.comms.server --port 50051

# On the client node (e.g. n2l-1), first a quick check (a few seconds):
uv run python -m edge_fl.comms.benchmark --config experiments/01_communication/config.yaml \
    --target 192.168.50.1:50051 --label h3plus --quick

# then the full sweep (1 KB to 50 MB, a few minutes per mode):
uv run python -m edge_fl.comms.benchmark --config experiments/01_communication/config.yaml \
    --target 192.168.50.1:50051 --label h3plus
```

Runs (tracker P1-04 to P1-06, and P1-09 for upload and download):

| Run | Server | Client | `--target` | `--label` |
|---|---|---|---|---|
| Loopback on the H3+ | H3+ | H3+ | `127.0.0.1:50051` | `h3plus` |
| Loopback on the N2L | n2l-1 | n2l-1 | `127.0.0.1:50051` | `n2l` |
| N2L → H3+ | H3+ | n2l-1 | `192.168.50.1:50051` | `h3plus` |
| H3+ → N2L | n2l-1 | H3+ | `192.168.50.2:50051` | `n2l` |

- The loopback runs show the cost of gRPC and Python on each board with no network. The
  cross-board runs add the network, so the difference between the two is the network's share.
- Upload and download only mean something between two boards, so loopback runs only need `echo`.
- Use the testbed switch only, not ZeroTier. Keep other traffic off the boards during a run.
- **After a `git pull`, restart the server too.** An old server doesn't know `Upload` or `Download`.

## Analysis

On the laptop, after copying the run folders back with `scp`:

```bash
uv run python experiments/01_communication/analyze_echo.py
```

It writes figures 1 to 5 and `phase1_summary.md` to `results/01_communication/analysis/`.
Figure 5 (upload against download) appears once upload/download runs exist.
