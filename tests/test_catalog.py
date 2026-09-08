from fmtless import catalog, decode

import pytest


def blob(*records):
    return b"".join(r.encode() + b"\0" for r in records)


def test_offsets_are_the_ids():
    entries = catalog.parse(blob("2|a.c|1|first", "3|a.c|2|second"))
    assert sorted(entries) == [0, 14]
    assert entries[14].fmt == "second"


def test_fields_are_pulled_apart():
    entry = catalog.parse(blob("4|src/pump.c|88|stalled"))[0]
    assert entry.level_name == "ERROR"
    assert entry.where == "src/pump.c:88"
    assert entry.fmt == "stalled"


def test_a_pipe_in_the_format_is_left_alone():
    entry = catalog.parse(blob("2|a.c|1|a | b | c"))[0]
    assert entry.fmt == "a | b | c"


def test_a_malformed_record_is_named():
    with pytest.raises(catalog.CatalogError):
        catalog.parse(blob("2|a.c|oops"))


def test_render_fills_the_holes_in_order():
    assert decode.render("{} of {}", [("uint", 3), ("uint", 7)]) == "3 of 7"


def test_render_honours_a_spec():
    assert decode.render("{:04x}", [("uint", 255)]) == "00ff"


def test_render_shows_a_hole_it_cannot_fill():
    assert decode.render("{} {}", [("uint", 1)]) == "1 {missing}"


def test_render_shows_an_argument_no_hole_wanted():
    assert "extra: 2" in decode.render("{}", [("uint", 1), ("uint", 2)])


def test_pointers_are_printed_as_hex():
    assert decode.render("at {}", [("ptr", 0x2000A1C0)]) == "at 0x2000a1c0"


def test_a_bad_spec_does_not_lose_the_value():
    assert "41.75" in decode.render("{:d}", [("f32", 41.75)])


def test_decode_needs_the_matching_catalog():
    with pytest.raises(decode.DecodeError):
        decode.decode(b"\x63", catalog.parse(blob("2|a.c|1|x")))


def test_a_cut_frame_is_flagged():
    entries = catalog.parse(blob("2|a.c|1|{}"))
    record = decode.decode(b"\x00\x03\x07\x0f", entries)
    assert record.truncated
    assert "truncated" in str(record)
