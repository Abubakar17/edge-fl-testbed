from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Payload(_message.Message):
    __slots__ = ("data", "seq")
    DATA_FIELD_NUMBER: _ClassVar[int]
    SEQ_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    seq: int
    def __init__(self, data: _Optional[bytes] = ..., seq: _Optional[int] = ...) -> None: ...

class Ack(_message.Message):
    __slots__ = ("seq", "received_bytes")
    SEQ_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_BYTES_FIELD_NUMBER: _ClassVar[int]
    seq: int
    received_bytes: int
    def __init__(self, seq: _Optional[int] = ..., received_bytes: _Optional[int] = ...) -> None: ...

class SizeRequest(_message.Message):
    __slots__ = ("seq", "size_bytes")
    SEQ_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    seq: int
    size_bytes: int
    def __init__(self, seq: _Optional[int] = ..., size_bytes: _Optional[int] = ...) -> None: ...
