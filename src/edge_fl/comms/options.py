"""gRPC settings shared by the server and the client."""

MB = 1024 * 1024

# gRPC rejects messages larger than 4 MB by default. The benchmark sends up to 50 MB,
# so both sides raise the limit. Matches grpc.max_message_mb in configs/network.example.yaml.
DEFAULT_MAX_MESSAGE_MB = 64

DEFAULT_PORT = 50051


def message_size_options(max_message_mb: int = DEFAULT_MAX_MESSAGE_MB) -> list[tuple[str, int]]:
    """Channel/server options that raise gRPC's send and receive size limits.

    The limits apply per side: the server must accept a large request, *and* the client
    must accept the equally large echo coming back, so both get the same options.
    """
    limit = max_message_mb * MB
    return [
        ("grpc.max_send_message_length", limit),
        ("grpc.max_receive_message_length", limit),
    ]
