"""edge_fl: a federated learning testbed for heterogeneous edge hardware.

Subpackages
-----------
comms    Phase 1. Device-to-device communication (gRPC) and its cost.
distopt  Phase 2. Distributed optimization (ADMM, decentralized GD) in NumPy.
fl       Phase 3. Federated learning with Flower (FedAvg, FedProx, FedADMM).
metrics  Measurement utilities shared by all phases (latency, bytes, energy).
common   Configuration, logging and other cross-cutting helpers.
"""

__version__ = "0.1.0"
