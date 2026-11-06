"""Federated learning server entry point (placeholder).

Will start the Flower server on the coordinator and select the aggregation
strategy (FedAvg, FedProx, FedADMM) from the experiment config.

Run with: ``python -m edge_fl.fl.server``
"""

import logging
import os

log = logging.getLogger(__name__)


def main() -> None:
    """Placeholder: log the configured address and exit."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    address = os.environ.get("EDGE_FL_SERVER_ADDRESS", "0.0.0.0:8080")
    log.info("server stub started (address=%s); not implemented yet", address)


if __name__ == "__main__":
    main()
