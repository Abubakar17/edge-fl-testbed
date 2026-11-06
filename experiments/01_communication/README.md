# Phase 1: Communication

Make the standalone devices exchange messages over gRPC, then measure what that costs.

**Questions**
- Round-trip latency between the coordinator and each client, and how it grows with payload size.
- Achievable throughput per link and in aggregate as more clients connect at once.
- How much of the cost is serialization (protobuf) and how much is transfer.

**Code:** `src/edge_fl/comms/`, `src/edge_fl/metrics/`
**Config:** [`config.yaml`](config.yaml)
**Outputs:** `results/01_communication/`
