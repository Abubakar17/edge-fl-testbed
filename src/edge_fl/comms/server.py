"""gRPC benchmark server: Echo, Upload and Download (see protos/echo.proto).

It does no work on the data, so a client timing the calls measures only transport:
serialization, HTTP/2 framing, TCP and the network.

Any node can run it (not only the coordinator), which keeps decentralized setups open.

Run:  python -m edge_fl.comms.server --port 50051
"""

from __future__ import annotations

import argparse
import logging
import os
from concurrent import futures

import grpc

from edge_fl.comms.options import DEFAULT_MAX_MESSAGE_MB, DEFAULT_PORT, message_size_options
from edge_fl.comms.protos import echo_pb2, echo_pb2_grpc

log = logging.getLogger(__name__)


class EchoServicer(echo_pb2_grpc.EchoServicer):
    """Implements the service in echo.proto. Method names are capitalised because the
    .proto fixes them."""

    def __init__(self) -> None:
        # Download payload cache: (size, bytes). Generating 50 MB of random bytes takes
        # time, so it happens once per size (on the client's untimed warm-up calls), never
        # inside a timed call. One entry is enough: the benchmark goes size by size.
        self._download_cache: tuple[int, bytes] = (0, b"")

    def Echo(self, request: echo_pb2.Payload, context: grpc.ServicerContext) -> echo_pb2.Payload:
        # Return the request object itself: no copy and no processing, so the server
        # adds as little time as possible to the measured round trip.
        return request

    def Upload(self, request: echo_pb2.Payload, context: grpc.ServicerContext) -> echo_pb2.Ack:
        # The payload has already been received and decoded by gRPC; reply with a tiny
        # receipt so the client can verify nothing was lost.
        return echo_pb2.Ack(seq=request.seq, received_bytes=len(request.data))

    def Download(
        self, request: echo_pb2.SizeRequest, context: grpc.ServicerContext
    ) -> echo_pb2.Payload:
        size = request.size_bytes
        if self._download_cache[0] != size:
            self._download_cache = (size, os.urandom(size))  # random: incompressible
        return echo_pb2.Payload(data=self._download_cache[1], seq=request.seq)


def start_server(
    host: str = "0.0.0.0",
    port: int = DEFAULT_PORT,
    max_message_mb: int = DEFAULT_MAX_MESSAGE_MB,
    workers: int = 4,
) -> tuple[grpc.Server, int]:
    """Start the echo server in background threads and return it with its bound port.

    ``port=0`` lets the OS pick a free port (used by the tests); the real port is
    returned so the caller knows where to connect.
    """
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=workers),  # one thread per concurrent call
        options=message_size_options(max_message_mb),
    )
    echo_pb2_grpc.add_EchoServicer_to_server(EchoServicer(), server)
    bound_port = server.add_insecure_port(f"{host}:{port}")  # plain TCP, no TLS on the testbed
    if bound_port == 0:
        raise RuntimeError(f"could not bind {host}:{port} (port in use?)")
    server.start()
    return server, bound_port


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0", help="interface to listen on (0.0.0.0 = all)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--max-message-mb", type=int, default=DEFAULT_MAX_MESSAGE_MB)
    parser.add_argument("--workers", type=int, default=4, help="max concurrent calls")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    server, port = start_server(args.host, args.port, args.max_message_mb, args.workers)
    log.info(
        "echo server listening on %s:%d (max message %d MB)", args.host, port, args.max_message_mb
    )
    try:
        server.wait_for_termination()  # block until Ctrl+C
    except KeyboardInterrupt:
        log.info("stopping")
        server.stop(grace=1.0)


if __name__ == "__main__":
    main()
