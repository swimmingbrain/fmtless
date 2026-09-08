"""The reading half of the wire format described in include/fmtless_wire.h."""

import struct

TAG_BOOL = 0x01
TAG_INT = 0x02
TAG_UINT = 0x03
TAG_F32 = 0x04
TAG_F64 = 0x05
TAG_STR = 0x06
TAG_PTR = 0x07
TAG_CHAR = 0x08
TAG_CUT = 0x0F


class WireError(Exception):
    pass


class Reader:
    """A cursor over one frame."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    @property
    def done(self) -> bool:
        return self.pos >= len(self.data)

    def byte(self) -> int:
        if self.done:
            raise WireError("frame ended in the middle of a value")
        b = self.data[self.pos]
        self.pos += 1
        return b

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise WireError("frame ended in the middle of a value")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def varint(self) -> int:
        value = 0
        shift = 0
        while True:
            b = self.byte()
            value |= (b & 0x7F) << shift
            if not b & 0x80:
                return value
            shift += 7
            if shift > 63:
                raise WireError("varint is too long to be real")


def unzigzag(v: int) -> int:
    return (v >> 1) ^ -(v & 1)


def read_value(r: Reader):
    """One tagged argument. Returns (kind, value); kind is the tag name."""
    tag = r.byte()
    if tag == TAG_BOOL:
        return "bool", bool(r.byte())
    if tag == TAG_INT:
        return "int", unzigzag(r.varint())
    if tag == TAG_UINT:
        return "uint", r.varint()
    if tag == TAG_F32:
        return "f32", struct.unpack("<f", r.take(4))[0]
    if tag == TAG_F64:
        return "f64", struct.unpack("<d", r.take(8))[0]
    if tag == TAG_STR:
        n = r.varint()
        return "str", r.take(n).decode("utf-8", "replace")
    if tag == TAG_PTR:
        return "ptr", r.varint()
    if tag == TAG_CHAR:
        return "char", chr(r.byte())
    if tag == TAG_CUT:
        return "cut", None
    raise WireError(f"unknown argument tag 0x{tag:02x}")


def cobs_decode(block: bytes) -> bytes:
    """One COBS block, without its trailing zero."""
    out = bytearray()
    pos = 0
    while pos < len(block):
        code = block[pos]
        if code == 0:
            raise WireError("a zero byte inside a COBS block")
        pos += 1
        end = pos + code - 1
        if end > len(block):
            raise WireError("COBS block claims more bytes than it has")
        out += block[pos:end]
        pos = end
        if code != 0xFF and pos < len(block):
            out.append(0)
    return bytes(out)


def frames(stream, framed: bool = True):
    """Yield frames from a byte iterator, splitting on the COBS delimiter.

    Reads whatever is available and keeps the remainder, so it works the same
    on a file that is already complete and on a serial port that dribbles.
    """
    if not framed:
        for chunk in stream:
            if chunk:
                yield chunk
        return

    buf = bytearray()
    for chunk in stream:
        buf += chunk
        while True:
            cut = buf.find(0)
            if cut < 0:
                break
            block, buf = bytes(buf[:cut]), buf[cut + 1 :]
            if block:
                yield cobs_decode(block)
    if buf:
        raise WireError("the stream ended in the middle of a frame")
