# Phase 1: Communication

Make the standalone devices exchange messages over gRPC, then measure what that costs.

**Questions**
- Round-trip latency between nodes, and how it grows with payload size.
- How close gRPC gets to the raw link, measured with `iperf3` in [`baseline/`](baseline/).
- How much of each round trip is protobuf serialization (CPU) rather than transfer, on x86 and on arm64.

**Code:** `src/edge_fl/comms/`: the `protos/echo.proto` contract, `server.py`, `client.py` and `benchmark.py`
**Config:** [`config.yaml`](config.yaml)
**Outputs:** `results/01_communication/<date>_<client>_to_<label>/`, containing `summary.csv`, `rtt_raw.csv`, `serialization.csv` and `meta.json`

## Baseline (raw network)

`baseline/` holds `ping` and `iperf3` for every pair of devices, plus `summarize_baseline.py`.
H3+ ↔ N2L: 0.48 ms RTT, 294 Mbit/s N2L → H3+, 335 Mbit/s H3+ → N2L.

## Running the echo benchmark

The server runs on one node and the benchmark on another. Round trips are timed on the
client only, so clock differences between boards don't matter.

```bash
# On the server node (e.g. the H3+):
uv run python -m edge_fl.comms.server --port 50051

# On the client node (e.g. n2l-1), first a quick check (a few seconds):
uv run python -m edge_fl.comms.benchmark --config experiments/01_communication/config.yaml \
    --target 192.168.50.1:50051 --label h3plus --quick

# then the full sweep (1 KB to 50 MB, a few minutes):
uv run python -m edge_fl.comms.benchmark --config experiments/01_communication/config.yaml \
    --target 192.168.50.1:50051 --label h3plus
```

Planned runs (tracker P1-04 to P1-06):

| Run | Server | Client | `--target` |
|---|---|---|---|
| Loopback on the H3+ | H3+ | H3+ | `127.0.0.1:50051` |
| Loopback on the N2L | n2l-1 | n2l-1 | `127.0.0.1:50051` |
| N2L → H3+ | H3+ | n2l-1 | `192.168.50.1:50051` |
| H3+ → N2L | n2l-1 | H3+ | `192.168.50.2:50051` |

The loopback runs show the cost of gRPC and Python on each board with no network. The
cross-board runs add the network, so the difference between the two is the network's share.

Use the testbed switch only, not ZeroTier. Keep other traffic off the boards during a run.
