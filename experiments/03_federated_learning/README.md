# Phase 3: Federated learning

Flower (flwr) on the physical testbed, comparing FedAvg with FedProx and FedADMM on
non-IID data. The phase also adds one differentiator, either update compression or
per-round energy measurement.

**Questions**
- How much non-IID data (Dirichlet alpha) degrades FedAvg, and how much FedProx and FedADMM recover.
- Accuracy against wall-clock time and against bytes communicated on real arm64 hardware.
- The differentiator: accuracy against communication for compressed updates, or joules per round.

**Code:** `src/edge_fl/fl/`
**Config:** [`config.yaml`](config.yaml)
**Outputs:** `results/03_federated_learning/`
