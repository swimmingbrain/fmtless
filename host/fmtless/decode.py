"""Turning a frame plus a catalog back into the line somebody wrote."""

import re
from dataclasses import dataclass, field

from . import wire

PLACEHOLDER = re.compile(r"\{(:[^}]*)?\}")


@dataclass
class Record:
    level: str
    where: str
    message: str
    id: int
    args: list = field(default_factory=list)
    truncated: bool = False

    def __str__(self) -> str:
        line = f"{self.level:<5} {self.where}  {self.message}"
        return line + "  [truncated]" if self.truncated else line


class DecodeError(Exception):
    pass


def decode(frame: bytes, entries: dict) -> Record:
    r = wire.Reader(frame)
    entry_id = r.varint()
    entry = entries.get(entry_id)
    if entry is None:
        raise DecodeError(
            f"id {entry_id} is not in the catalog; the ELF and the device "
            f"are probably out of step"
        )

    args, truncated = [], False
    while not r.done:
        kind, value = wire.read_value(r)
        if kind == "cut":
            truncated = True
            break
        args.append((kind, value))

    return Record(
        level=entry.level_name,
        where=entry.where,
        message=render(entry.fmt, args),
        id=entry_id,
        args=[v for _, v in args],
        truncated=truncated,
    )


def render(fmt: str, args: list) -> str:
    """Fill the {} holes left in the format string.

    The spec after a colon is Python's, so {:04x} and {:.2f} mean what you
    would expect. A hole with no argument, or an argument no hole wants, is
    shown rather than hidden: a decoder that quietly drops half a line is
    worse than one that admits it.
    """
    out, used = [], 0
    at = 0
    for hole in PLACEHOLDER.finditer(fmt):
        out.append(fmt[at : hole.start()])
        at = hole.end()
        if used >= len(args):
            out.append("{missing}")
            continue
        kind, value = args[used]
        used += 1
        out.append(_one(kind, value, hole.group(1)))
    out.append(fmt[at:])

    text = "".join(out)
    if used < len(args):
        extra = ", ".join(_one(k, v, None) for k, v in args[used:])
        text += f"  [extra: {extra}]"
    return text


def _one(kind: str, value, spec) -> str:
    if kind == "ptr" and not spec:
        return f"0x{value:x}"
    if not spec:
        if kind in ("f32", "f64"):
            return repr(round(value, 6)) if value != int(value) else f"{value:.1f}"
        return str(value)
    try:
        return format(value, spec[1:])
    except (ValueError, TypeError):
        return f"{value}{{bad spec {spec}}}"
