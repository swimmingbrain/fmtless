"""Just enough ELF to find one section.

pyelftools would do this too, but the whole point of the host tool is that it
drops into a build without dragging anything along, so the ~60 lines that read
a section header table live here instead.
"""

import struct


class ElfError(Exception):
    pass


class Elf:
    """A parsed ELF file, opened only far enough to read its sections."""

    def __init__(self, data: bytes):
        if len(data) < 64 or data[:4] != b"\x7fELF":
            raise ElfError("not an ELF file")

        self.bits = {1: 32, 2: 64}.get(data[4])
        if self.bits is None:
            raise ElfError(f"unknown ELF class {data[4]}")
        endian = {1: "<", 2: ">"}.get(data[5])
        if endian is None:
            raise ElfError(f"unknown ELF endianness {data[5]}")

        self._data = data
        self._end = endian
        self.machine = struct.unpack_from(endian + "H", data, 18)[0]

        if self.bits == 64:
            e_shoff, = struct.unpack_from(endian + "Q", data, 40)
            e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(
                endian + "HHH", data, 58
            )
        else:
            e_shoff, = struct.unpack_from(endian + "I", data, 32)
            e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(
                endian + "HHH", data, 46
            )

        if e_shoff == 0 or e_shnum == 0:
            raise ElfError("the file has no section headers")

        self._headers = [
            self._section_header(e_shoff + i * e_shentsize) for i in range(e_shnum)
        ]
        if e_shstrndx >= len(self._headers):
            raise ElfError("the section name table is out of range")
        names = self._section_bytes(self._headers[e_shstrndx])
        for header in self._headers:
            end = names.find(b"\0", header["name_off"])
            header["name"] = names[header["name_off"] : end].decode("utf-8", "replace")

    def _section_header(self, at: int) -> dict:
        d, e = self._data, self._end
        if self.bits == 64:
            name, type_, flags, addr, off, size = struct.unpack_from(
                e + "IIQQQQ", d, at
            )
        else:
            name, type_, flags, addr, off, size = struct.unpack_from(
                e + "IIIIII", d, at
            )
        return {
            "name_off": name,
            "type": type_,
            "flags": flags,
            "addr": addr,
            "offset": off,
            "size": size,
        }

    def _section_bytes(self, header: dict) -> bytes:
        if header["type"] == 8:  # SHT_NOBITS occupies no file space
            return b""
        start = header["offset"]
        return self._data[start : start + header["size"]]

    def section(self, name: str):
        """Contents and load address of a section, or None if it is absent."""
        for header in self._headers:
            if header["name"] == name:
                return self._section_bytes(header), header["addr"]
        return None

    def section_names(self):
        return [h["name"] for h in self._headers if h["name"]]


def read(path: str) -> Elf:
    with open(path, "rb") as fp:
        return Elf(fp.read())
