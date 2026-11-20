"""gRPC echo client: connects to an echo server and sends payloads.

This module only sends and receives. Timing and statistics live in the benchmark
(Step 3), so the client stays a thin wrapper around the generated stub.

Quick check from the command line:
    python -m edge_fl.comms.client --target 192.168.50.1:50051 --size-kb 1024
"""

from __future__ import annotations

import argparse
import time
from types import TracebackType

import grpc

from edge_fl.comms.options import DEFAULT_MAX_MESSAGE_MB, DEFAULT_PORT, message_size_options
from edge_fl.comms.protos import echo_pb2, echo_pb2_grpc


class EchoClient:
    """A connection to one echo server.

    One channel (one TCP connection) is opened in ``__init__`` and reused for every call,
    so connection setup is never part of a measured round trip.
    Use it as a context manager so the connection is always closed::

        with EchoClient("192.168.50.1:50051") as client:
            reply = client.echo(b"hello")
    """

    def __init__(
        self,
        target: str,
        max_message_mb: int = DEFAULT_MAX_MESSAGE_MB,
        connect_timeout_s: float = 10.0,
    ) -> None:
        self.target = target
        self._channel = grpc.insecure_channel(target, options=message_size_options(max_message_mb))
        # Channels connect lazily; wait here so a wrong address fails now, clearly,
        # instead of on the first measured call.
        try:
            grpc.channel_ready_future(self._channel).result(timeout=connect_timeout_s)
        except grpc.FutureTimeoutError as exc:
            self._channel.close()
            raise ConnectionError(f"no echo server reachable at {target}") from exc
        self._stub = echo_pb2_grpc.EchoStub(self._channel)

    def echo(self, data: bytes, seq: int = 0, timeout_s: float | None = 60.0) -> echo_pb2.Payload:
        """Send ``data`` and return the server's reply (which should be identical)."""
        return self._stub.Echo(echo_pb2.Payload(data=data, seq=seq), timeout=timeout_s)

    def close(self) -> None:
        self._channel.close()

    def __enter__(self) -> EchoClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Send one payload to an echo server and check the reply."
    )
    parser.add_argument(
        "--target", default=f"127.0.0.1:{DEFAULT_PORT}", help="host:port of the server"
    )
    parser.add_argument("--size-kb", type=int, default=1)
    parser.add_argument("--max-message-mb", type=int, default=DEFAULT_MAX_MESSAGE_MB)
    args = parser.parse_args(argv)

    data = bytes(args.size_kb * 1024)
    with EchoClient(args.target, args.max_message_mb) as client:
        start = time.perf_counter()
        reply = client.echo(data, seq=1)
        elapsed_ms = (time.perf_counter() - start) * 1000
    status = "OK" if reply.data == data and reply.seq == 1 else "MISMATCH"
    print(
        f"{args.size_kb} KB to {args.target}: {status}, "
        f"{elapsed_ms:.3f} ms (single call, not a benchmark)"
    )


if __name__ == "__main__":
    main()
