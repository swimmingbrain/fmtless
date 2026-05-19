/* fmtless - logging for C that leaves the words at home.
 *
 * A log line has two halves: the text, which never changes, and the values,
 * which do. printf ships both, every time, and formats them on the device.
 * fmtless ships only the values.
 *
 * The text of every call site is gathered into an ELF section that the linker
 * keeps in the file and out of the image, so it costs no flash. What the
 * device sends is the offset the linker gave that text, followed by the
 * arguments. A host holding the same ELF turns the two back into your line.
 *
 *     fmtless_info("pump {} at {} rpm", id, rpm);
 *
 *     on the wire   2b 03 07 03 fa 0b        six bytes
 *     on the host   INFO  pump.c:88  pump 7 at 1530 rpm
 *
 * One header. Define FMTLESS_IMPLEMENTATION in exactly one translation unit,
 * provide fmtless_sink(), and point the host tool at your ELF. There is
 * nothing to initialise, nothing to allocate, and no libc needed.
 *
 * SPDX-License-Identifier: MIT
 * https://github.com/swimmingbrain/fmtless
 */
#ifndef FMTLESS_H
#define FMTLESS_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------ config */

#define FMTLESS_TRACE 0
#define FMTLESS_DEBUG 1
#define FMTLESS_INFO 2
#define FMTLESS_WARN 3
#define FMTLESS_ERROR 4
#define FMTLESS_OFF 5

/* Lines below this leave nothing behind: no code, and no catalog entry, so
 * the text is not even in the ELF. */
#ifndef FMTLESS_LEVEL
#  define FMTLESS_LEVEL FMTLESS_TRACE
#endif

/* Largest payload one call may build, on the stack, before framing. */
#ifndef FMTLESS_MAX_FRAME
#  define FMTLESS_MAX_FRAME 96
#endif

/* Name of the catalog section, as a bare identifier. It has to stay a valid
 * one, because the linker derives __start_<name> from it and the ids are
 * measured against that. Change it only if it clashes with something. */
#ifndef FMTLESS_SECTION
#  define FMTLESS_SECTION fmtless
#endif

/* You provide this. It receives one whole frame at a time and may do anything
 * with it: a UART, RTT, a ring buffer, a file. */
void fmtless_sink(const uint8_t *frame, size_t len);

/* ------------------------------------------------------------- wire format */

/* Argument tags. Only the integer sign and the float width are distinguished,
 * the varint carries the magnitude, so int and long cost the same. */
#define FMTLESS_TAG_BOOL 0x01
#define FMTLESS_TAG_INT 0x02  /* zigzag varint */
#define FMTLESS_TAG_UINT 0x03 /* varint */
#define FMTLESS_TAG_F32 0x04
#define FMTLESS_TAG_F64 0x05
#define FMTLESS_TAG_STR 0x06 /* varint length, then the bytes */
#define FMTLESS_TAG_PTR 0x07
#define FMTLESS_TAG_CHAR 0x08

/* Closes a frame that did not fit, so a cut line is reported, not invented. */
#define FMTLESS_TAG_CUT 0x0f

typedef struct {
  uint8_t *buf;
  size_t cap;
  size_t len;
  int cut; /* set once something did not fit */
} fmtless_enc;

/* These are real functions rather than inline ones on purpose: a call site
 * should cost a handful of calls, not its own copy of the encoder. */
void fmtless_enc_init(fmtless_enc *e, uint8_t *buf, size_t cap);
void fmtless_put_id(fmtless_enc *e, uint32_t id);
void fmtless_put_bool(fmtless_enc *e, int v);
void fmtless_put_char(fmtless_enc *e, char v);
void fmtless_put_int(fmtless_enc *e, long long v);
void fmtless_put_uint(fmtless_enc *e, unsigned long long v);
void fmtless_put_f32(fmtless_enc *e, float v);
void fmtless_put_f64(fmtless_enc *e, double v);
void fmtless_put_str(fmtless_enc *e, const char *s);
void fmtless_put_ptr(fmtless_enc *e, const void *p);

/* Frames what was encoded and hands it to fmtless_sink. */
void fmtless_emit(fmtless_enc *e);

/* Exposed for tests and for anyone framing on their own. Returns the bytes
 * written, including the trailing zero, or 0 if it did not fit. */
size_t fmtless_cobs_encode(const uint8_t *in, size_t len, uint8_t *out,
                           size_t cap);

/* ------------------------------------------------------------------ macros */

#define FMTLESS_CAT_(a, b) a##b
#define FMTLESS_CAT(a, b) FMTLESS_CAT_(a, b)
#define FMTLESS_STR_(x) #x
#define FMTLESS_STR(x) FMTLESS_STR_(x)

/* The linker invents this for any section whose name is a valid C identifier.
 * Ids are offsets from it, so they stay small and survive a position
 * independent build, where a bare address would not. */
extern const char FMTLESS_CAT(__start_, FMTLESS_SECTION)[];

/* One catalog entry, written straight into the section as text.
 *
 * The section flags are empty on purpose. A section without SHF_ALLOC is kept
 * in the ELF and never loaded, so the linker still hands out an address for
 * every entry while objcopy leaves the whole thing behind.
 *
 * Fields are separated by | and the format comes last, so a | inside the
 * format needs no escaping. A " or a \ inside it does, since the text passes
 * through the assembler. */
#define FMTLESS_ENTRY(sym, level, fmt)                                         \
  __asm__(".pushsection " FMTLESS_STR(FMTLESS_SECTION) ",\"\",%progbits\n"     \
          FMTLESS_STR(sym) ":\n"                                               \
          ".asciz \"" FMTLESS_STR(level) "|" __FILE__                          \
          "|" FMTLESS_STR(__LINE__) "|" fmt "\"\n"                             \
          ".popsection\n");                                                    \
  extern const char sym[]

/* Every supported type lands on one of the encoders. long and long long share
 * one: the varint makes the width irrelevant. */
#define FMTLESS_PUT(e, x)                                                      \
  _Generic((x),                                                                \
      _Bool: fmtless_put_bool,                                                 \
      char: fmtless_put_char,                                                  \
      signed char: fmtless_put_int,                                            \
      unsigned char: fmtless_put_uint,                                         \
      short: fmtless_put_int,                                                  \
      unsigned short: fmtless_put_uint,                                        \
      int: fmtless_put_int,                                                    \
      unsigned int: fmtless_put_uint,                                          \
      long: fmtless_put_int,                                                   \
      unsigned long: fmtless_put_uint,                                         \
      long long: fmtless_put_int,                                              \
      unsigned long long: fmtless_put_uint,                                    \
      float: fmtless_put_f32,                                                  \
      double: fmtless_put_f64,                                                 \
      char *: fmtless_put_str,                                                 \
      const char *: fmtless_put_str,                                           \
      void *: fmtless_put_ptr,                                                 \
      const void *: fmtless_put_ptr)((e), (x))

/* The format rides along in the variadic list, so the list is never empty and
 * none of this needs the GNU comma swallowing extension. The count therefore
 * includes the format, and FMTLESS_ARGS_n steps over it. */
#define FMTLESS_FIRST(...) FMTLESS_FIRST_(__VA_ARGS__, 0)
#define FMTLESS_FIRST_(a, ...) a

#define FMTLESS_NARG(...)                                                      \
  FMTLESS_NARG_(__VA_ARGS__, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0)
#define FMTLESS_NARG_(_1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13,  \
                      n, ...)                                                  \
  n

#define FMTLESS_ARGS_1(e, fmt)
#define FMTLESS_ARGS_2(e, fmt, a1) FMTLESS_PUT(e, a1);
#define FMTLESS_ARGS_3(e, fmt, a1, a2)                                         \
  FMTLESS_ARGS_2(e, fmt, a1) FMTLESS_PUT(e, a2);
#define FMTLESS_ARGS_4(e, fmt, a1, a2, a3)                                     \
  FMTLESS_ARGS_3(e, fmt, a1, a2) FMTLESS_PUT(e, a3);
#define FMTLESS_ARGS_5(e, fmt, a1, a2, a3, a4)                                 \
  FMTLESS_ARGS_4(e, fmt, a1, a2, a3) FMTLESS_PUT(e, a4);
#define FMTLESS_ARGS_6(e, fmt, a1, a2, a3, a4, a5)                             \
  FMTLESS_ARGS_5(e, fmt, a1, a2, a3, a4) FMTLESS_PUT(e, a5);
#define FMTLESS_ARGS_7(e, fmt, a1, a2, a3, a4, a5, a6)                         \
  FMTLESS_ARGS_6(e, fmt, a1, a2, a3, a4, a5) FMTLESS_PUT(e, a6);
#define FMTLESS_ARGS_8(e, fmt, a1, a2, a3, a4, a5, a6, a7)                     \
  FMTLESS_ARGS_7(e, fmt, a1, a2, a3, a4, a5, a6) FMTLESS_PUT(e, a7);
#define FMTLESS_ARGS_9(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8)                 \
  FMTLESS_ARGS_8(e, fmt, a1, a2, a3, a4, a5, a6, a7) FMTLESS_PUT(e, a8);
#define FMTLESS_ARGS_10(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9)            \
  FMTLESS_ARGS_9(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8) FMTLESS_PUT(e, a9);
#define FMTLESS_ARGS_11(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10)       \
  FMTLESS_ARGS_10(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9)                  \
  FMTLESS_PUT(e, a10);
#define FMTLESS_ARGS_12(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11)  \
  FMTLESS_ARGS_11(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10)             \
  FMTLESS_PUT(e, a11);
#define FMTLESS_ARGS_13(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11,  \
                        a12)                                                   \
  FMTLESS_ARGS_12(e, fmt, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11)        \
  FMTLESS_PUT(e, a12);

#define FMTLESS_ARGS(e, ...)                                                   \
  FMTLESS_CAT(FMTLESS_ARGS_, FMTLESS_NARG(__VA_ARGS__))(e, __VA_ARGS__)

#define FMTLESS_LOG_AT_(counter, level, ...)                                   \
  do {                                                                         \
    FMTLESS_ENTRY(FMTLESS_CAT(fmtless_entry_, counter), level,                 \
                  FMTLESS_FIRST(__VA_ARGS__));                                 \
    uint8_t fmtless_buf_[FMTLESS_MAX_FRAME];                                   \
    fmtless_enc fmtless_e_;                                                    \
    fmtless_enc_init(&fmtless_e_, fmtless_buf_, sizeof fmtless_buf_);          \
    fmtless_put_id(&fmtless_e_,                                                \
                   (uint32_t)(FMTLESS_CAT(fmtless_entry_, counter) -           \
                              FMTLESS_CAT(__start_, FMTLESS_SECTION)));        \
    FMTLESS_ARGS(&fmtless_e_, __VA_ARGS__)                                     \
    fmtless_emit(&fmtless_e_);                                                 \
  } while (0)

#define FMTLESS_LOG_(level, ...)                                               \
  FMTLESS_LOG_AT_(__COUNTER__, level, __VA_ARGS__)

#define FMTLESS_NOP_ ((void)0)

#if FMTLESS_LEVEL <= FMTLESS_TRACE
#  define fmtless_trace(...) FMTLESS_LOG_(FMTLESS_TRACE, __VA_ARGS__)
#else
#  define fmtless_trace(...) FMTLESS_NOP_
#endif

#if FMTLESS_LEVEL <= FMTLESS_DEBUG
#  define fmtless_debug(...) FMTLESS_LOG_(FMTLESS_DEBUG, __VA_ARGS__)
#else
#  define fmtless_debug(...) FMTLESS_NOP_
#endif

#if FMTLESS_LEVEL <= FMTLESS_INFO
#  define fmtless_info(...) FMTLESS_LOG_(FMTLESS_INFO, __VA_ARGS__)
#else
#  define fmtless_info(...) FMTLESS_NOP_
#endif

#if FMTLESS_LEVEL <= FMTLESS_WARN
#  define fmtless_warn(...) FMTLESS_LOG_(FMTLESS_WARN, __VA_ARGS__)
#else
#  define fmtless_warn(...) FMTLESS_NOP_
#endif

#if FMTLESS_LEVEL <= FMTLESS_ERROR
#  define fmtless_error(...) FMTLESS_LOG_(FMTLESS_ERROR, __VA_ARGS__)
#else
#  define fmtless_error(...) FMTLESS_NOP_
#endif

#ifdef __cplusplus
}
#endif

#endif /* FMTLESS_H */

/* ---------------------------------------------------------- implementation */

#ifdef FMTLESS_IMPLEMENTATION
#ifndef FMTLESS_IMPLEMENTED
#define FMTLESS_IMPLEMENTED

#ifdef __cplusplus
extern "C" {
#endif

void
fmtless_enc_init(fmtless_enc *e, uint8_t *buf, size_t cap) {
  e->buf = buf;
  e->cap = cap;
  e->len = 0;
  e->cut = 0;
}

static void
fmtless_byte_(fmtless_enc *e, uint8_t b) {
  if (e->len < e->cap)
    e->buf[e->len++] = b;
  else
    e->cut = 1;
}

/* base 128, low group first, high bit means another group follows */
static void
fmtless_varint_(fmtless_enc *e, uint64_t v) {
  while (v >= 0x80) {
    fmtless_byte_(e, (uint8_t)(v | 0x80));
    v >>= 7;
  }
  fmtless_byte_(e, (uint8_t)v);
}

void
fmtless_put_id(fmtless_enc *e, uint32_t id) {
  fmtless_varint_(e, id);
}

void
fmtless_put_bool(fmtless_enc *e, int v) {
  fmtless_byte_(e, FMTLESS_TAG_BOOL);
  fmtless_byte_(e, v ? 1u : 0u);
}

void
fmtless_put_char(fmtless_enc *e, char v) {
  fmtless_byte_(e, FMTLESS_TAG_CHAR);
  fmtless_byte_(e, (uint8_t)v);
}

/* small negatives should cost as little as small positives */
void
fmtless_put_int(fmtless_enc *e, long long v) {
  uint64_t zigzag = ((uint64_t)v << 1) ^ (uint64_t)(v >> 63);
  fmtless_byte_(e, FMTLESS_TAG_INT);
  fmtless_varint_(e, zigzag);
}

void
fmtless_put_uint(fmtless_enc *e, unsigned long long v) {
  fmtless_byte_(e, FMTLESS_TAG_UINT);
  fmtless_varint_(e, (uint64_t)v);
}

/* Floats go out little endian a byte at a time, so this needs no string.h and
 * does not care how the target keeps them in memory. */
void
fmtless_put_f32(fmtless_enc *e, float v) {
  union {
    float f;
    uint32_t u;
  } bits;
  int i;
  bits.f = v;
  fmtless_byte_(e, FMTLESS_TAG_F32);
  for (i = 0; i < 4; i++)
    fmtless_byte_(e, (uint8_t)(bits.u >> (8 * i)));
}

void
fmtless_put_f64(fmtless_enc *e, double v) {
  union {
    double f;
    uint64_t u;
  } bits;
  int i;
  bits.f = v;
  fmtless_byte_(e, FMTLESS_TAG_F64);
  for (i = 0; i < 8; i++)
    fmtless_byte_(e, (uint8_t)(bits.u >> (8 * i)));
}

void
fmtless_put_str(fmtless_enc *e, const char *s) {
  size_t n = 0, i;
  while (s && s[n])
    n++;
  fmtless_byte_(e, FMTLESS_TAG_STR);
  fmtless_varint_(e, (uint64_t)n);
  for (i = 0; i < n; i++)
    fmtless_byte_(e, (uint8_t)s[i]);
}

void
fmtless_put_ptr(fmtless_enc *e, const void *p) {
  fmtless_byte_(e, FMTLESS_TAG_PTR);
  fmtless_varint_(e, (uint64_t)(uintptr_t)p);
}

/* Consistent overhead byte stuffing. The block comes out free of zero bytes,
 * so one zero can end it, and a reader joining mid stream only has to wait
 * for the next one. Worst case is one extra byte per 254. */
size_t
fmtless_cobs_encode(const uint8_t *in, size_t len, uint8_t *out, size_t cap) {
  size_t read, write = 1, code_at = 0;
  uint8_t code = 1;

  if (cap == 0)
    return 0;
  for (read = 0; read < len; read++) {
    if (in[read] == 0) {
      out[code_at] = code;
      code_at = write++;
      code = 1;
      if (write > cap)
        return 0;
      continue;
    }
    if (write >= cap)
      return 0;
    out[write++] = in[read];
    if (++code == 0xff && read + 1 < len) {
      out[code_at] = code;
      code_at = write++;
      code = 1;
      if (write > cap)
        return 0;
    }
  }
  out[code_at] = code;
  if (write >= cap)
    return 0;
  out[write++] = 0x00; /* delimiter */
  return write;
}

void
fmtless_emit(fmtless_enc *e) {
  if (e->cut && e->cap)
    e->buf[e->cap - 1] = FMTLESS_TAG_CUT;

#ifdef FMTLESS_NO_COBS
  fmtless_sink(e->buf, e->len);
#else
  {
    uint8_t framed[FMTLESS_MAX_FRAME + FMTLESS_MAX_FRAME / 254 + 2];
    size_t n = fmtless_cobs_encode(e->buf, e->len, framed, sizeof framed);
    if (n)
      fmtless_sink(framed, n);
  }
#endif
}

#ifdef __cplusplus
}
#endif

#endif /* FMTLESS_IMPLEMENTED */
#endif /* FMTLESS_IMPLEMENTATION */
