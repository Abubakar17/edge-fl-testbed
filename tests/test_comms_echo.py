"""The echo server and client work together on this machine (loopback)."""

from collections.abc import Iterator

import pytest

from edge_fl.comms.client import EchoClient
from edge_fl.comms.options import MB
from edge_fl.comms.server import start_server


@pytest.fixture
def server_target() -> Iterator[str]:
    # port=0: the OS picks a free port, so tests never clash with a running server.
    server, port = start_server(host="127.0.0.1", port=0)
    yield f"127.0.0.1:{port}"
    server.stop(grace=None)


def test_echo_returns_same_bytes(server_target: str) -> None:
    with EchoClient(server_target) as client:
        reply = client.echo(b"hello testbed", seq=7)
    assert reply.data == b"hello testbed"
    assert reply.seq == 7


def test_payload_above_default_4mb_limit(server_target: str) -> None:
    # 5 MB would be rejected by gRPC's default 4 MB limit; this proves it was raised.
    data = bytes(5 * MB)
    with EchoClient(server_target) as client:
        reply = client.echo(data)
    assert len(reply.data) == len(data)


def test_unreachable_server_fails_fast() -> None:
    with pytest.raises(ConnectionError):
        EchoClient("127.0.0.1:1", connect_timeout_s=0.5)
