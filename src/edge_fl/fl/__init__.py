"""Phase 3: federated learning with Flower (flwr).

Planned contents
----------------
- ``server.py``     Flower server / ServerApp on the coordinator; strategy
                    selection (FedAvg, FedProx, FedADMM) from config.
- ``client.py``     Flower client / ClientApp on each board (CPU-only PyTorch).
- ``strategies/``   Custom strategies not shipped with Flower (e.g. FedADMM).
- ``data.py``       Federated dataset loading with non-IID partitioning
                    (e.g. Dirichlet label skew).
- ``models.py``     Small models that fit within 2-4 GB RAM on arm64.
- ``compression.py`` / ``energy.py``  The differentiator: update compression
                    or per-round energy measurement (to be decided).
"""
