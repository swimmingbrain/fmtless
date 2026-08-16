/* The same program twice, once with fmtless and once with a printf, so the
 * cost of the words can be measured rather than argued about.
 *
 *     make -C examples/cortex-m
 *
 * Both are compiled for a Cortex-M4 and never linked, because linking a printf
 * drags in a C library and the point here is only the code and the constants
 * each call site leaves behind.
 */
#include <stdint.h>

#define UART_DR (*(volatile uint32_t *)0x4000C000u)

#if USE_PRINTF

/* the ordinary way: the text is a constant in flash and the formatting runs
 * on the device */
extern int printf(const char *fmt, ...);

#  define LOG_BOOT(board) printf("boot, board %s\n", board)
#  define LOG_OFFSET(o) printf("calibration offset %d\n", o)
#  define LOG_TEMP(t) printf("die temperature %f C\n", t)
#  define LOG_ALIGN(p) printf("frame buffer at %p is not aligned\n", p)
#  define LOG_SENSOR(id, ms)                                                   \
    printf("sensor %u did not answer in %u ms, giving up\n", id, ms)
#  define LOG_PLAIN() printf("no arguments at all\n")
#  define LOG_KEPT(a, b, c) printf("%u of %u lines kept, %u dropped\n", a, b, c)
#  define LOG_LOOP(n, us) printf("loop %u took %f us\n", n, us)

#else

#  define FMTLESS_IMPLEMENTATION
#  include "fmtless.h"

void
fmtless_sink(const uint8_t *frame, size_t len) {
  for (size_t i = 0; i < len; i++)
    UART_DR = frame[i];
}

#  define LOG_BOOT(board) fmtless_info("boot, board {}", board)
#  define LOG_OFFSET(o) fmtless_debug("calibration offset {}", o)
#  define LOG_TEMP(t) fmtless_info("die temperature {} C", t)
#  define LOG_ALIGN(p) fmtless_warn("frame buffer at {} is not aligned", p)
#  define LOG_SENSOR(id, ms)                                                   \
    fmtless_error("sensor {} did not answer in {} ms, giving up", id, ms)
#  define LOG_PLAIN() fmtless_info("no arguments at all")
#  define LOG_KEPT(a, b, c)                                                    \
    fmtless_info("{} of {} lines kept, {} dropped", a, b, c)
#  define LOG_LOOP(n, us) fmtless_trace("loop {} took {} us", n, us)

#endif

void
run(const char *board, int16_t offset, float temperature, void *handle) {
  LOG_BOOT(board);
  LOG_OFFSET(offset);
  LOG_ALIGN(handle);
  LOG_SENSOR(3u, 250u);
  LOG_PLAIN();
  LOG_KEPT(998u, 1000u, 2u);
#if !NO_FLOATS
  /* a printf that has to format a float drags in a lot of C library, so the
   * comparison is worth seeing both with these two and without */
  LOG_TEMP(temperature);
  LOG_LOOP(4096u, 91.5);
#else
  (void)temperature;
#endif
}
