# Engineering log

A dated journal of decisions, measurements and problems. Newest entries go at the top.

---

## 2026-11-20: Phase 1 closed, handover to Phase 2

**Working now**
- **Testbed:** H3+ and n2l-1 on a dedicated switch (`192.168.50.0/24`). The H3+ provides NAT
  and time sync, and NAT survives reboots. Both boards run the project (`make test` passes on
  x86_64 and arm64). Setup is in `docs/setup.md`.
- **gRPC layer:** `src/edge_fl/comms/` holds an Echo/Upload/Download server and client. Any node
  can serve, which keeps decentralized setups open, and the message limit is 64 MB.
- **Benchmark and analysis:** `benchmark.py` runs size sweeps with warmup and automatic repeat
  counts, and writes raw samples plus metadata. `analysis.py` and `analyze_echo.py` compute the
  raw-link floor and the latency–bandwidth model, and produce 5 figures and summary tables.
  21 tests pass.

**Phase 1 results** (detail in the entries below and in the README)
- Large messages reach 86–90% of raw TCP: about 288 Mbit/s to the N2L, about 265 from it.
- Small messages are set by the CPU, not the network: about 1.7 ms per call with the H3+ as
  server, about 3.7 ms with an N2L as server.
- Echo model (N2L client): 1.7 ms + 2·size / 285 Mbit/s.

**Left open in Phase 1**
- Concurrency (P1-07) waits for more N2Ls.
- An optional test of the CPU governor (P1-10), for the case where a bigger message is faster.

**Phase 2: next steps**
1. Get the optimization problem from Giulio (Q-09). Requirements are in
   `experiments/02_distributed_optimization/README.md`.
2. Write the centralized baseline, then data partitioning, then consensus ADMM, then
   decentralized gradient descent. Simulate first in a single process, then run over gRPC on
   the boards.
3. Estimate the communication cost per iteration from the Phase 1 model. With small vectors
   it is about α per message, so the number of rounds dominates.

## 2026-11-20 (evening): upload and download measured separately

**Runs.** `--modes upload download` with the H3+ as server (n2l-1 as client), then with
n2l-1 as server (H3+ as client). Each data-flow direction is therefore measured twice,
once with each board as client.

| Size | H3+ → N2L (N2L downloads) | H3+ → N2L (H3+ uploads) | N2L → H3+ (H3+ downloads) | N2L → H3+ (N2L uploads) |
|---|---|---|---|---|
| 1 KB | 1.71 ms | 3.68 ms | 3.72 ms | 1.74 ms |
| 1 MB | 29.7 ms (282 Mbit/s) | 36.7 ms (229) | 33.8 ms (248) | 37.3 ms (225) |
| 4 MB | 112 ms (300) | 133 ms (252) | 128 ms (262) | 133 ms (253) |
| 50 MB | 1.46 s (287) | 1.45 s (289) | 1.56 s (268) | 1.61 s (261) |

**Findings**
- **For large messages, direction matters and client role doesn't.** At 50 MB the two measurements of
  each direction agree to within 1% (H3+ → N2L: 287 against 289 Mbit/s) and 3% (N2L → H3+: 268 against 261).
  - Data flows **H3+ → N2L at about 288 Mbit/s** (86% of iperf3's 335).
  - Data flows **N2L → H3+ at about 265 Mbit/s** (90% of iperf3's 294).
  - The N2L sends about 8% slower than it receives, the same direction as iperf3's 12%.
- **For small messages, role matters and direction doesn't.** A 1 KB call costs about 1.7 ms whenever the H3+
  is the server, and about 3.7 ms whenever the N2L is the server, whichever way the data goes. This matches
  the echo finding (N2L as server: 3.5 ms). The N2L's per-call cost as a server dominates small messages.
- **The N2L-as-server cost *falls* as messages grow:** H3+ uploads take 3.68 ms at 1 KB but 3.23 ms at 64 KB.
  The echo runs show the same (3.50 → 3.31 ms from 1 to 16 KB). A bigger message should never be faster.
  - Hypothesis, not yet tested: CPU frequency scaling on the N2L. Between small requests it idles and
    clocks down, and larger payloads keep it busy enough to clock up.
  - Test: set the `performance` governor on n2l-1 and repeat the small sizes.
  - Relevant to Phase 2 and decentralized FL, which send many small messages to N2L servers.
- **Consistency:** upload + download equals echo + one α. The gap is +1.6 to 2 ms with the N2L as client and
  +3.9 to 4.7 ms with the N2L as server; at 50 MB it is only +1.6 to 3.2%.
- **FL estimate for a 4 MB model on an N2L client:** download 112 ms + upload 133 ms ≈ 245 ms of
  communication per round, with the upload about 19% slower than the download at that size.

**Caveat:** the fitted one-way bandwidths differ from the measured 50 MB plateau by up to 5%,
because one α can't describe a small-message cost that depends on the server. Quote the
plateau values for bandwidth.

## 2026-11-20 (later): Phase 1 results on the boards, and analysis

**Runs.** Each scenario got a `--quick` check, then a full sweep:
- H3+ loopback
- N2L loopback
- N2L → H3+
- H3+ → N2L

The loopback runs used the board's own testbed IP; Linux routes that internally, so it is
still loopback. The run folders were collected to the laptop with `scp`.

| Size | H3+ loopback | N2L loopback | N2L → H3+ | H3+ → N2L |
|---|---|---|---|---|
| 1 KB | 0.38 ms | 3.10 ms | 1.82 ms | 3.50 ms |
| 64 KB | 0.62 ms | 4.10 ms | 5.33 ms | 5.65 ms |
| 1 MB | 4.1 ms | 14.5 ms | 62 ms (269 Mbit/s) | 60 ms (281 Mbit/s) |
| 50 MB | 381 ms | 381 ms | 2.97 s (282 Mbit/s) | 2.96 s (283 Mbit/s) |

**Findings**
- **Large messages reach about 90% of raw TCP.** Throughput levels off at about 283 Mbit/s in both
  directions. The echo-equivalent iperf3 rate (harmonic mean of 294 and 335) is 313 Mbit/s.
  At 50 MB the raw-link floor is 2.68 s against 2.97 s measured.
- **For small messages, the N2L's CPU costs more than the network.** The network is only 15 to 29% of a
  1 KB round trip. The N2L loopback takes 3.1 ms against 0.38 ms on the H3+, so the N2L is about 8× slower.
- **Being the server costs the N2L about twice as much as being the client:** 3.5 ms against 1.8 ms for 1 KB.
  The likely cause is the Python gRPC server handing each request to a worker thread (inferred, not measured).
  This matters for decentralized FL, where every node is a server.
- **Latency-bandwidth model** (relative least squares):
  - N2L → H3+: 1.71 ms + 2·size / 285 Mbit/s, within 4% at every size.
  - H3+ → N2L: 2.91 ms + 2·size / 300 Mbit/s, within 15%.
  - The crossover from CPU-bound to link-bound is around 64 to 256 KB.
- **Stability:** board-to-board runs vary by 1 to 2% at 1 MB, and no sample exceeds 3× the median. The H3+
  is the noisy node (desktop session, Docker, NAT and chrony share it).

**Caveats**
- An echo can't separate upload from download.
- Serialization times above 16 MB mostly measure memory allocation, and vary 2 to 3× between H3+ runs.
- The largest sizes have only 10 to 31 samples.

**Code**
- `run()` now connects before creating the run folder, so a failed start leaves no empty folder.
  There's a regression test and a `connect_timeout_s` setting.
- Analysis is split in two:
  - `src/edge_fl/comms/analysis.py`: numpy only, tested. Run selection, raw-link floor, model fit.
  - `experiments/01_communication/analyze_echo.py`: 4 figures and summary tables written to
    `results/01_communication/analysis/`.
- The figures were checked visually for overlapping labels.

**Next:** `Upload` and `Download` calls, to measure each direction separately (what FL actually does).

## 2026-11-20: Phase 1 gRPC echo benchmark (code)

**Contract and generated code.**
- `src/edge_fl/comms/protos/echo.proto` defines `Payload {bytes data; uint64 seq}` and a unary `Echo` call.
- `make protos` generates the Python code with `-I src`, so the generated imports are package-relative.
- The generated files are committed, so the boards don't need the generator.
- `grpcio-tools` is capped at 1.81. Version 1.85 needs protobuf 7, which conflicts with flwr's protobuf <7. Code generated by 1.81 runs fine on the grpcio 1.85 runtime.

**Server and client.**
- The server returns the request object unchanged, so it adds almost nothing to the round trip.
- Any node can run it, which keeps decentralized setups open.
- Both sides raise gRPC's 4 MB message limit to 64 MB (`options.py`); one test sends 5 MB to prove it.
- The client opens one connection and reuses it, so connection setup is never timed.
- The client fails fast on an unreachable server.

**Benchmark (`benchmark.py`).** For each payload size, 1 KB to 50 MB:
1. Check the full echo once, untimed.
2. Make 20 warmup calls that aren't counted.
3. Make N timed calls, with the garbage collector paused. N = 500 MB ÷ size, kept between 10 and 500.
4. Time protobuf encode and decode separately, with no network.

Each run writes `summary.csv`, `rtt_raw.csv` (every sample), `serialization.csv` and
`meta.json` (machine, versions, config). The config is validated with pydantic, so an
unknown key is an error.

**Laptop loopback check.** This is not a testbed result, just a check that the code works.
- The full sweep takes 48 s.
- Small messages take about 0.5 ms with no network at all. That is gRPC and Python overhead alone, about the same as the testbed's network RTT (0.48 ms).
- Large payloads plateau at about 1.5 to 1.7 Gbit/s, limited by CPU and memory copying.
- At 50 MB, encode plus decode takes about 78 ms per hop on this x86 laptop.
- Expect all of this to be slower on the N2L.

**Next:** loopback runs on the H3+ and on n2l-1, then N2L → H3+ and H3+ → N2L.

## 2026-11-13 (later): NAT persistence, n2l-1 software, baseline measurements

**NAT now starts automatically at boot (C-07).**
- `/etc/sysctl.d/99-testbed-nat.conf` sets `ip_forward=1`.
- `/usr/local/sbin/testbed-nat.sh` adds the three NAT and forwarding rules. It checks first, so it never adds duplicates.
- `testbed-nat.service` runs the script at boot, after Docker.
- I didn't use `iptables-persistent`, because it would also save and restore Docker's own rules and create duplicates.

**n2l-1 software (C-08).**
- Set the hostname to `n2l-1`, including the `127.0.1.1` line in `/etc/hosts`.
- Switched off conda's automatic base environment, which clashes with uv.
- Installed git, make, curl, iperf3, Docker and uv, and cloned the repo.
- `make test` passes, the project's first run on arm64.
- `lsusb -t` confirms the Ethernet adapter (driver r8152) runs at USB 2.0 speed, 480M.

**Baseline measurements (P1-00).**
- iperf3 servers ran on both boards, and the laptop was always the client, using `-R` for the reverse direction so no firewall change was needed.
- Pings always ran from a Linux board.
- 3 rounds: 100 pings, or a 30 s single-stream TCP test, per round.
- `experiments/01_communication/summarize_baseline.py` reduces the files to medians in `baseline_summary.csv`.

| Test | Link | Median | Spread (3 rounds) | Notes |
|---|---|---|---|---|
| ping RTT | H3+ ↔ N2L | 0.483 ms | 0.473-0.483 | std dev 0.051 ms, 0% loss |
| ping RTT | H3+ ↔ laptop | 0.734 ms | 0.712-0.736 | std dev 0.098 ms, 0% loss |
| ping RTT | N2L ↔ laptop | 0.714 ms | 0.703-0.771 | std dev 0.178 ms, 0% loss, one 3.7 ms outlier |
| iperf3 | H3+ → N2L | 335.3 Mbit/s | 335.27-335.28 | 1 retransmit |
| iperf3 | N2L → H3+ | 293.9 Mbit/s | 293.90-293.92 | 0 retransmits |
| iperf3 | H3+ → laptop | 94.9 Mbit/s | 94.86-94.89 | 0 retransmits |
| iperf3 | laptop → H3+ | 94.8 Mbit/s | 94.78-94.81 | Windows sender doesn't report retransmits |
| iperf3 | laptop → N2L | 94.8 Mbit/s | 94.75-94.79 | |
| iperf3 | N2L → laptop | 94.9 Mbit/s | 94.87-94.89 | 0 retransmits |

**Findings**
- **The laptop's Ethernet port is Fast Ethernet** ("Realtek PCIe FE Family Controller", 100 Mbps
  in `Get-NetAdapter`). That is a hardware limit, not the cable or the switch. 94.8 Mbit/s is
  the most TCP can carry over 100 Mbit/s, so every laptop figure measures the laptop's port.
  The ~940 Mbit/s expected for laptop ↔ H3+ isn't reachable. **The laptop controls runs but
  isn't a measurement node.** A USB 3.0 gigabit adapter would fix it if it's ever needed.
- **H3+ ↔ N2L runs at 294 to 335 Mbit/s,** consistent with the USB 2.0 adapter (480M bus).
  The adapter is not 100 Mbit/s, because it's well above 94. The N2L's adapter is the
  bottleneck; the switch and the H3+ have headroom.
- **Sending is the N2L's weak direction,** about 12% slower than receiving (294 vs 335). The
  extra CPU and USB work of transmitting costs more. In FL, a client uploading its update
  will be slower than downloading the model.
- **Latency is sub-millisecond with no loss, and very repeatable** (the spread between rounds
  is under 1%). The laptop paths add about 0.25 ms, mostly Windows' network stack.
- **The floor for Phase 1:** gRPC is judged against about 0.48 ms per round trip and about
  294 Mbit/s of N2L upload. Even on the raw link, 10 MB takes at least 0.27 s from an N2L.

**Next:** Phase 1 gRPC echo benchmark between the boards.
- Payloads from 1 KB to 50 MB, with round trips timed on the client.
- Raise gRPC's 4 MB message limit, or use streaming.
- Run Docker with `--network host`.

## 2026-11-13: Testbed network and first N2L

**Layout.** The H3+, the laptop and N2L #1 are connected through a TP-Link 16-port gigabit
switch on `192.168.50.0/24`:

| Device | Address |
|---|---|
| H3+ | `.1` on `enp2s0` |
| Laptop | `.100`, no gateway, so internet stays on Wi-Fi |
| N2L #1 | `.2`, on a USB 2.0 Ethernet adapter |

The H3+'s other port, `enp1s0`, takes the lab cable by DHCP. The full procedure is in
[`setup.md`](setup.md).

**Problems and fixes**
- *Ping from the H3+ returned "Destination Host Unreachable".* The address was on the
  unplugged port. Moved it to the profile bound to `enp2s0`.
- *The laptop didn't answer ping.* Windows Firewall blocks it. Added an inbound ICMPv4 echo rule.
- *H3+ internet broke.* The switch profile carried a stray gateway with a better route
  metric. Removed the gateway and set `never-default`.
- *Internet tests failed.* The lab network blocks ping, so internet is now tested with `curl -I`.
- *N2L internet.* The H3+ now shares its lab connection through NAT. The FORWARD rules
  are inserted at position 1 because Docker drops forwarded traffic by default.
- *N2L TLS errors ("certificate not yet valid").* The N2L has no clock battery. Fixed with
  chrony: the H3+ serves time, and the N2Ls are its clients.
- *The H3+ Wi-Fi is unusable.* Its login page never appears.

**Decisions**
- N2L Ethernet adapters go in the **USB 2.0** port, because Hardkernel says USB 3.0 Ethernet
  adapters are unreliable on the N2L. That caps N2L links at about 250 to 320 Mbit/s, so
  they are expected to be the throughput bottleneck.
- Round-trip times are measured on one node only, because clocks agree to just 0.1 to 1 ms.

**To do**
- Make the NAT rules and `ip_forward` on the H3+ persistent.
- Give N2L #1 its unique hostname.
- Install Docker and uv on N2L #1.
- Baseline `ping` and `iperf3` for every pair of devices.

**Questions for Giulio**
- Was the old `172.16.1.x` address on the H3+ part of a planned addressing scheme?
- Should the USB 3.0 Ethernet adapters in the hardware order be changed?
- FL topology: centralized first and then decentralized, or decentralized only?

The board is now referred to as the H3+. The 2026-11-06 entry said it reported as an H3,
so check `lscpu`: an N6005 CPU means H3+, an N5105 means H3.

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
