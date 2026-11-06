"""Measurement utilities shared by all phases.

Planned contents
----------------
- ``timing.py``  High-resolution timers and per-round / per-message latency.
- ``network.py`` Bytes sent/received per message and per round (payload cost).
- ``system.py``  CPU, memory and temperature sampling on the boards.
- ``energy.py``  Per-round energy, if an external power meter is available.
- ``recorder.py`` A single results writer (CSV/JSON under ``results/``) so every
                  experiment produces the same, plottable format.
"""
