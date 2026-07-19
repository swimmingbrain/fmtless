"""Compile the example, run it, decode what it produced.

This is the test that matters: it exercises the assembler trick, the linker,
the encoder on the device side and the whole host tool in one go. If the
catalog section ever stops being emitted, or an id stops lining up, this fails.
"""

import shutil
import subprocess

import pytest

from fmtless import catalog, decode, wire

COMPILERS = [cc for cc in ("gcc", "clang") if shutil.which(cc)]

EXPECTED = [
    "INFO  {src}:28  boot, board vector-r3",
    "DEBUG {src}:29  calibration offset -294",
    "INFO  {src}:30  die temperature 41.75 C",
    "WARN  {src}:31  frame buffer at 0x2000a1c0 is not aligned",
    "ERROR {src}:32  sensor 3 did not answer in 250 ms, giving up",
    "INFO  {src}:33  no arguments at all",
    "INFO  {src}:34  998 of 1000 lines kept, 2 dropped",
    "TRACE {src}:35  loop 4096 took 91.5 us",
]


@pytest.fixture(scope="module", params=COMPILERS or ["none"])
def built(request, tmp_path_factory, repo_root):
    if not COMPILERS:
        pytest.skip("no C compiler on PATH")
    out = tmp_path_factory.mktemp("build") / f"demo-{request.param}"
    # built from the repo root with a relative path, so __FILE__ in the
    # catalog reads the way it would in a real build
    subprocess.run(
        [
            request.param, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic",
            "-Iinclude", "-o", str(out), "examples/hosted/demo.c",
        ],
        check=True,
        cwd=repo_root,
    )
    frames = subprocess.run([str(out)], check=True, capture_output=True).stdout
    return out, frames


def records_of(built):
    elf_path, frames = built
    entries = catalog.from_elf(str(elf_path))
    return [decode.decode(f, entries) for f in wire.frames([frames])]


def test_every_line_comes_back(built):
    src = "examples/hosted/demo.c"
    got = [str(r) for r in records_of(built)]
    assert got == [line.format(src=src) for line in EXPECTED]


def test_the_catalog_holds_one_entry_per_call(built):
    entries = catalog.from_elf(str(built[0]))
    assert len(entries) == len(EXPECTED)


def test_no_format_text_reaches_the_image(built):
    """The words live in the ELF, so they must not be in a loaded segment."""
    elf_path, _ = built
    loaded = subprocess.run(
        ["objcopy", "-O", "binary", str(elf_path), str(elf_path) + ".bin"],
        capture_output=True,
    )
    if loaded.returncode != 0:
        pytest.skip("objcopy is not available")
    image = (elf_path.parent / (elf_path.name + ".bin")).read_bytes()
    assert b"did not answer in" not in image
    assert b"calibration offset" not in image


def test_the_wire_is_smaller_than_the_words(built):
    _elf, frames = built
    rendered = sum(len(r.message) for r in records_of(built))
    assert len(frames) < rendered


def test_a_frame_from_another_build_is_refused(built):
    entries = catalog.from_elf(str(built[0]))
    with pytest.raises(decode.DecodeError):
        decode.decode(b"\xf0\x7f", entries)
