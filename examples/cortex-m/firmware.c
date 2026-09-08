/* the entry point the size comparison links, kept out of blink.c so the two
   variants differ only in how they log */
#include <stdint.h>

void run(const char *board, int16_t offset, float temperature, void *handle);

int
main(void) {
  run("vector-r3", -294, 41.75f, (void *)0x2000a1c0);
  for (;;) {
  }
}
