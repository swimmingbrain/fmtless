# fmtless

Logging for C that leaves the words at home.

A log line has two halves: the text, which never changes, and the values, which
do. `printf` ships both, every time, and formats them on the device. fmtless
ships only the values.

```c
fmtless_info("pump {} at {} rpm", id, rpm);
```

```
on the wire   2b 03 07 03 fa 0b            six bytes
on the host   INFO  pump.c:88  pump 7 at 1530 rpm
```

The text never reaches the device at all. It is gathered into an ELF section
the linker keeps in the file and out of the image, so it costs no flash. What
goes over the link is the offset the linker gave that text, followed by the
arguments. A host holding the same ELF puts the two back together.

One header, one Python tool, no dependencies on either side.

## What it costs

The same eight log lines, built for a Cortex-M4 at `-Os` and linked with
newlib-nano, once through `printf` and once through fmtless:

| | flash |
| --- | --- |
| fmtless | 1 132 B |
| `printf` | 73 424 B |

`printf` is expensive here because asking a C library to format on the device
pulls the whole formatter in. A hand written tiny printf lands in the low
kilobytes instead, which is a fairer fight, but two things do not change: its
format strings still sit in flash, and it still formats on the device. Reproduce
the numbers with `make -C examples/cortex-m compare`.

The link is cheaper too. Those eight lines are 490 bytes once rendered and
79 bytes on the wire, and the 200 bytes of format text they came from stayed
in the ELF.

## Try it without hardware

```console
$ make run
INFO  examples/hosted/demo.c:28  boot, board vector-r3
DEBUG examples/hosted/demo.c:29  calibration offset -294
INFO  examples/hosted/demo.c:30  die temperature 41.75 C
WARN  examples/hosted/demo.c:31  frame buffer at 0x2000a1c0 is not aligned
ERROR examples/hosted/demo.c:32  sensor 3 did not answer in 250 ms, giving up
INFO  examples/hosted/demo.c:33  no arguments at all
INFO  examples/hosted/demo.c:34  998 of 1000 lines kept, 2 dropped
TRACE examples/hosted/demo.c:35  loop 4096 took 91.5 us
```

That is the real thing: a C program logging through the same header firmware
would use, its frames piped into the decoder.

## Using it

Drop `include/fmtless.h` into your project. In one translation unit:

```c
#define FMTLESS_IMPLEMENTATION
#include "fmtless.h"

void fmtless_sink(const uint8_t *frame, size_t len) {
    while (len--)
        uart_put(*frame++);
}
```

Everywhere else, just include it and log:

```c
fmtless_trace("loop {} took {} us", n, elapsed);
fmtless_debug("calibration offset {}", offset);
fmtless_info("boot, board {}", board_name);
fmtless_warn("frame buffer at {} is not aligned", ptr);
fmtless_error("sensor {} did not answer in {} ms", id, timeout);
```

Then point the host tool at the ELF you flashed:

```console
$ pip install fmtless
$ fmtless decode --elf build/firmware.elf --port /dev/ttyUSB0 --baud 115200
$ fmtless catalog --elf build/firmware.elf     # everything it could ever say
```

`decode` reads stdin by default, so it also takes a capture file or the output
of anything that already has the bytes. `--json` gives one object per line.

## How the catalog works

This is the whole trick, and it is worth a paragraph.

Each call site emits its text through inline assembly into a section named
`fmtless`, with the section flags left empty:

```
.pushsection fmtless,"",%progbits
fmtless_entry_7:
.asciz "2|src/pump.c|88|pump {} at {} rpm"
.popsection
```

A section with no `SHF_ALLOC` is written to the ELF and never loaded, so the
linker still assigns every entry an address while `objcopy -O binary` drops the
lot. Because the section name is a valid C identifier, the linker also invents
`__start_fmtless`, and the id the device sends is just the distance between the
two, which stays small enough to be one or two bytes of varint.

So the id costs nothing to compute, the text costs nothing to store, and the
decoder finds it by reading the section straight out of the ELF.

## The wire

A frame is the id as a varint, then one argument after another. Every argument
carries a one byte tag, so the decoder never guesses, and integers are varints,
so a small number is one byte whether it was written as an `int` or a `long`.

Frames are COBS encoded and end with a zero byte, which is what you want on a
UART: no length prefix to lose, and a reader that joins halfway through only
has to wait for the next zero. `FMTLESS_NO_COBS` turns that off if your
transport already knows where messages end.

A line that does not fit in `FMTLESS_MAX_FRAME` is sent with a cut marker
rather than dropped, and the decoder says so.

## Levels

`FMTLESS_LEVEL` sets the floor at compile time. Anything below it expands to
nothing: no code, and no catalog entry either, so the text is not even in the
ELF.

```c
#define FMTLESS_LEVEL FMTLESS_WARN
```

## What it does not do

- **The format string is not checked against the arguments.** `_Generic` picks
  an encoder per argument, so the types on the wire are always right, but
  nothing counts your `{}` at compile time. A hole with no argument, or an
  argument with no hole, shows up in the decoded line rather than being hidden.
- **A `"` or a `\` in a format string needs escaping**, because the text passes
  through the assembler on its way into the section.
- **The ELF and the device have to match.** An id the catalog does not know is
  reported as exactly that, which is usually a sign you flashed one build and
  are decoding with another.
- **Up to twelve arguments per line.** Raise it by extending the `FMTLESS_ARGS_n`
  list if you really need to.
- **No timestamps.** The device knows the time, not the library; put it in the
  frame yourself as an argument if you want it.

## Requirements

C11, for `_Generic`. GCC or Clang, for the section attribute and `__COUNTER__`.
The header includes only `stddef.h` and `stdint.h`, so it builds with
`-ffreestanding` on a target with no C library at all. The host tool needs
Python 3.8 and nothing else, except `pyserial` if you use `--port`.

Tested with GCC and Clang on x86-64, and with `arm-none-eabi-gcc` for
Cortex-M.

## Running the tests

```console
make test
```

Which compiles the example with every compiler it can find, runs it, decodes
the frames and checks the lines come back exactly as written, on top of the
unit tests for the wire format and the catalog parser.

## Prior art

Rust has [defmt](https://github.com/knurling-rs/defmt), which is where the idea
of deferring the formatting to the host comes from, and it is excellent.
[Postform](https://github.com/Javier-varez/Postform) does it for C++. fmtless is
for plain C, in one header, with a decoder that reads a normal ELF and needs
nothing installed.

## License

MIT.
