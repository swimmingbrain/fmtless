/* A device that happens to be your PC.
 *
 * It logs the same mix of things firmware logs and writes the frames to
 * stdout, so the decoder can be driven without any hardware:
 *
 *     make demo
 *     ./build/demo | fmtless decode --elf build/demo
 */
#include <stdio.h>
#include <stdlib.h>

#define FMTLESS_IMPLEMENTATION
#include "fmtless.h"

/* the one thing the library asks of you */
void
fmtless_sink(const uint8_t *frame, size_t len) {
  fwrite(frame, 1, len, stdout);
}

int
main(void) {
  const char *board = "vector-r3";
  float temperature = 41.75f;
  int16_t offset = -294;
  void *handle = (void *)0x2000a1c0;

  fmtless_info("boot, board {}", board);
  fmtless_debug("calibration offset {}", offset);
  fmtless_info("die temperature {} C", temperature);
  fmtless_warn("frame buffer at {} is not aligned", handle);
  fmtless_error("sensor {} did not answer in {} ms, giving up", 3u, 250u);
  fmtless_info("no arguments at all");
  fmtless_info("{} of {} lines kept, {} dropped", 998u, 1000u, 2u);
  fmtless_trace("loop {} took {} us", 4096u, 91.5);

  fflush(stdout);
  return 0;
}
