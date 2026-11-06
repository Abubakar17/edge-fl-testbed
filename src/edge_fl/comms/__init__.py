"""Phase 1: communication between standalone devices.

Planned contents
----------------
- ``protos/``      Protobuf service definitions (e.g. an echo/ping service and a
                   tensor-exchange service with configurable payload size).
- ``server.py``    gRPC server that runs on the coordinator (ODROID-H3+).
- ``client.py``    gRPC client that runs on each ODROID-N2L.
- ``benchmark.py`` Drivers for round-trip latency, throughput/bandwidth and
                   serialization (payload) cost, sweeping message size and
                   number of concurrent clients.

Results are recorded with :mod:`edge_fl.metrics` so they are comparable across
phases.
"""
