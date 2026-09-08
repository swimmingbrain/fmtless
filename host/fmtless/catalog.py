"""The catalog: everything the firmware could ever say, read out of its ELF.

Each entry is one NUL terminated record the assembler placed in the catalog
section, and its offset in that section is the id the device puts on the wire.
"""

from dataclasses import dataclass

from . import elf

SECTION = "fmtless"

LEVEL_NAMES = {0: "TRACE", 1: "DEBUG", 2: "INFO", 3: "WARN", 4: "ERROR"}


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    id: int
    level: int
    file: str
    line: int
    fmt: str

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, f"LVL{self.level}")

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"


def parse(blob: bytes) -> dict:
    """Section bytes to {id: Entry}."""
    entries = {}
    offset = 0
    for record in blob.split(b"\0"):
        if record:
            entries[offset] = _entry(offset, record)
        offset += len(record) + 1
    return entries


def _entry(offset: int, record: bytes) -> Entry:
    text = record.decode("utf-8", "replace")
    # level|file|line|format, and the format keeps any | of its own
    parts = text.split("|", 3)
    if len(parts) != 4:
        raise CatalogError(f"catalog entry at {offset} is malformed: {text!r}")
    level, path, line, fmt = parts
    try:
        return Entry(offset, int(level), path, int(line), fmt)
    except ValueError:
        raise CatalogError(
            f"catalog entry at {offset} has a bad level or line: {text!r}"
        ) from None


def from_elf(path: str) -> dict:
    """Read the catalog out of an ELF, with a useful message if it is absent."""
    image = elf.read(path)
    found = image.section(SECTION)
    if found is None:
        raise CatalogError(
            f"{path} has no '{SECTION}' section, so it was not built with "
            f"fmtless, or the linker script dropped it"
        )
    blob, _addr = found
    if not blob:
        raise CatalogError(f"the '{SECTION}' section in {path} is empty")
    return parse(blob)
