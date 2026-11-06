# Engineering log

A dated journal of decisions, measurements and problems. Newest entries go at the top.

---

## 2026-11-06: Coordinator (ODROID-H3) bring-up

- The board reports as an x86 ODROID-H3 (not H3+): 4 cores, 8 GB RAM, 500 GB NVMe, Ubuntu MATE 22.04. Switched the system language from Italian to English.
- Wi-Fi dongle: Realtek 8811AU/8821AU. Installed its driver, and it sees nearby networks. The board was first online through phone tethering and is now on wired Ethernet.
- Remote access: installed an SSH server and joined ZeroTier, so the laptop can reach the board from another network. The address is kept out of the repo.
- Installed Docker and Compose, fixed the docker group permission, and confirmed `hello-world` runs. Also installed git, make, curl, tmux and uv.
- Cloned the repo to `~/edge-fl-testbed`. `make test` passes. `make sim` starts the server and three clients, which exit cleanly (they are still stubs).
- Still open: SSH key login, hostname (still `odroid-H3`), and `docs/setup.md`.
- Questions for the supervisor: when the N2Ls will be available and whether they are 2 GB or 4 GB, which network to use long term, whether ZeroTier is acceptable, and whether there is a power meter.
- Measurement note: Phase 1 benchmarks should go over the lab switch, not ZeroTier or the internet.

## 2026-11-06: Project initialized

- Scaffolded the repository: uv-managed Python 3.11 project with a src layout (`edge_fl`), a folder per phase under `experiments/`, YAML configs, Ansible and Docker deployment, and CI.
- Locked dependencies in `uv.lock`. Linux builds take torch from the PyTorch CPU-only index, so neither the arm64 boards nor the amd64 coordinator pull CUDA.
- Hardware details (board count, RAM, network) are still unconfirmed, so everything hardware-specific is in `configs/*.example.yaml`.
- Next: confirm the hardware inventory, then start Phase 1 (gRPC ping-pong and payload benchmarks).
