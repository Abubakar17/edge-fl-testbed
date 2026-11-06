"""Federated learning client entry point (placeholder).

Will start a Flower client on an edge board, load its local (non-IID) data
partition and train a CPU-only PyTorch model.

Run with: ``python -m edge_fl.fl.client``
"""

import logging
import os

log = logging.getLogger(__name__)


def main() -> None:
    """Placeholder: log the client identity and exit."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    client_id = os.environ.get("EDGE_FL_CLIENT_ID", "0")
    server = os.environ.get("EDGE_FL_SERVER_ADDRESS", "server:8080")
    log.info("client stub %s started (server=%s); not implemented yet", client_id, server)


if __name__ == "__main__":
    main()
