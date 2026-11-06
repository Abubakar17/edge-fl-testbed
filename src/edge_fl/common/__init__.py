"""Cross-cutting helpers used by every phase.

Planned contents
----------------
- ``config.py``  Pydantic models for ``configs/*.yaml`` (devices, network,
                 experiment) and a YAML loader with validation. Nothing about
                 the hardware is hardcoded: board count, roles, RAM and
                 addresses all come from config.
- ``logging.py`` Consistent, device-tagged logging setup.
- ``seed.py``    Seeding NumPy / PyTorch for reproducible runs.
"""
