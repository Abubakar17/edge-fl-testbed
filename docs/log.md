# Engineering log

A dated journal of decisions, measurements and problems. Newest entries go at the top.

---

## 2026-11-06: Project initialized

- Scaffolded the repository: uv-managed Python 3.11 project with a src layout (`edge_fl`), a folder per phase under `experiments/`, YAML configs, Ansible and Docker deployment, and CI.
- Locked dependencies in `uv.lock`. Linux builds take torch from the PyTorch CPU-only index, so neither the arm64 boards nor the amd64 coordinator pull CUDA.
- Hardware details (board count, RAM, network) are still unconfirmed, so everything hardware-specific is in `configs/*.example.yaml`.
- Next: confirm the hardware inventory, then start Phase 1 (gRPC ping-pong and payload benchmarks).
