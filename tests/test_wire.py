from fmtless import wire

import pytest


def enc_varint(v):
    """Mirror of fmtless_put_varint, so the tests read both directions."""
    out = bytearray()
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v)
    return bytes(out)


@pytest.mark.parametrize("value", [0, 1, 127, 128, 300, 2**32 - 1, 2**63 - 1])
def test_varint_round_trip(value):
    assert wire.Reader(enc_varint(value)).varint() == value


def test_varint_is_little_endian_base_128():
    assert enc_varint(300) == b"\xac\x02"


@pytest.mark.parametrize("value", [0, -1, 1, -64, 64, -(2**31), 2**31 - 1])
def test_zigzag_round_trip(value):
    encoded = (value << 1) ^ (value >> 63)
    assert wire.unzigzag(encoded) == value


def test_zigzag_keeps_small_negatives_small():
    assert len(enc_varint((-1 << 1) ^ (-1 >> 63))) == 1


def test_varint_that_never_ends_is_rejected():
    with pytest.raises(wire.WireError):
        wire.Reader(b"\x80" * 12).varint()


def test_reading_past_the_end_is_rejected():
    with pytest.raises(wire.WireError):
        wire.Reader(b"\x06\x05ab").take(5)


def test_cobs_decodes_a_block_without_zeros():
    assert wire.cobs_decode(b"\x03ab") == b"ab"


def test_cobs_restores_an_embedded_zero():
    assert wire.cobs_decode(b"\x02a\x02b") == b"a\x00b"


def test_cobs_rejects_a_zero_inside_a_block():
    with pytest.raises(wire.WireError):
        wire.cobs_decode(b"\x02a\x00")


def test_cobs_rejects_a_run_longer_than_the_block():
    with pytest.raises(wire.WireError):
        wire.cobs_decode(b"\x09ab")


def test_frames_splits_on_the_delimiter():
    stream = [b"\x03ab\x00\x03cd\x00"]
    assert list(wire.frames(stream)) == [b"ab", b"cd"]


def test_frames_joins_chunks_that_split_a_frame():
    stream = [b"\x03a", b"b\x00\x03cd", b"\x00"]
    assert list(wire.frames(stream)) == [b"ab", b"cd"]


def test_frames_complains_about_a_frame_that_never_ends():
    with pytest.raises(wire.WireError):
        list(wire.frames([b"\x03ab"]))


def test_values_carry_their_type():
    frame = b"\x03\xac\x02" + b"\x02\x01" + b"\x06\x02hi"
    r = wire.Reader(frame)
    assert wire.read_value(r) == ("uint", 300)
    assert wire.read_value(r) == ("int", -1)
    assert wire.read_value(r) == ("str", "hi")
    assert r.done


def test_unknown_tag_is_reported():
    with pytest.raises(wire.WireError):
        wire.read_value(wire.Reader(b"\x7f"))
