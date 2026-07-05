"""fmtless: read frames off a device and print what the firmware meant."""

import argparse
import json
import sys

from . import catalog, decode, wire

__version__ = "0.1.0"


def _chunks(fp, size=4096):
    while True:
        chunk = fp.read(size)
        if not chunk:
            return
        yield chunk


def _serial_chunks(port, baud):
    try:
        import serial  # optional, only needed for --port
    except ImportError:
        raise SystemExit(
            "reading a serial port needs pyserial: pip install pyserial"
        ) from None
    with serial.Serial(port, baud, timeout=0.2) as tty:
        while True:
            waiting = tty.in_waiting or 1
            chunk = tty.read(waiting)
            if chunk:
                yield chunk


def cmd_decode(args) -> int:
    entries = catalog.from_elf(args.elf)

    if args.port:
        stream = _serial_chunks(args.port, args.baud)
    elif args.input:
        stream = _chunks(open(args.input, "rb"))
    else:
        stream = _chunks(sys.stdin.buffer)

    failures = 0
    for frame in wire.frames(stream, framed=not args.raw):
        try:
            record = decode.decode(frame, entries)
        except (wire.WireError, decode.DecodeError) as exc:
            failures += 1
            print(f"?? {exc}", file=sys.stderr)
            if args.strict:
                return 1
            continue
        if args.json:
            print(
                json.dumps(
                    {
                        "level": record.level,
                        "where": record.where,
                        "message": record.message,
                        "id": record.id,
                        "args": record.args,
                        "truncated": record.truncated,
                    }
                ),
                flush=True,
            )
        else:
            print(record, flush=True)
    return 1 if failures and args.strict else 0


def cmd_catalog(args) -> int:
    entries = catalog.from_elf(args.elf)
    total = 0
    for entry_id in sorted(entries):
        entry = entries[entry_id]
        total += len(entry.fmt)
        if args.json:
            print(
                json.dumps(
                    {
                        "id": entry.id,
                        "level": entry.level_name,
                        "file": entry.file,
                        "line": entry.line,
                        "format": entry.fmt,
                    }
                )
            )
        else:
            print(f"{entry.id:>6}  {entry.level_name:<5} {entry.where:<28} {entry.fmt}")
    if not args.json:
        print(
            f"\n{len(entries)} entries, {total} bytes of text that stayed off "
            f"the device",
            file=sys.stderr,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fmtless",
        description="Decode fmtless log frames using the firmware's ELF.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command", required=True)

    d = subs.add_parser("decode", help="turn frames into log lines")
    d.add_argument("--elf", required=True, help="the ELF the device is running")
    d.add_argument("--input", help="read frames from a file instead of stdin")
    d.add_argument("--port", help="read frames from a serial port")
    d.add_argument("--baud", type=int, default=115200, help="baud rate for --port")
    d.add_argument(
        "--raw",
        action="store_true",
        help="frames arrive already delimited, so they are not COBS encoded",
    )
    d.add_argument("--json", action="store_true", help="one JSON object per line")
    d.add_argument(
        "--strict", action="store_true", help="stop at the first frame that fails"
    )
    d.set_defaults(func=cmd_decode)

    c = subs.add_parser("catalog", help="list everything the firmware can say")
    c.add_argument("--elf", required=True)
    c.add_argument("--json", action="store_true", help="one JSON object per line")
    c.set_defaults(func=cmd_catalog)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (catalog.CatalogError, wire.WireError) as exc:
        print(f"fmtless: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
