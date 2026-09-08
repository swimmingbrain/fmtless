# fmtless: a header for the device, a small Python tool for the host.
# There is nothing to build for the library itself.

CC      ?= cc
CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -Wpedantic
BUILD   ?= build

.PHONY: all demo test lint clean arm

all: demo

$(BUILD):
	@mkdir -p $(BUILD)

demo: $(BUILD)
	$(CC) $(CFLAGS) -Iinclude -o $(BUILD)/demo examples/hosted/demo.c

# what the demo says, decoded back
run: demo
	@./$(BUILD)/demo | PYTHONPATH=host python3 -m fmtless.cli decode --elf $(BUILD)/demo

test: demo
	PYTHONPATH=host python3 -m pytest tests -q

# proves the catalog survives a firmware link with --gc-sections
arm: $(BUILD)
	arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb $(CFLAGS) -Iinclude \
	  -ffunction-sections -fdata-sections -c \
	  -o $(BUILD)/arm.o examples/cortex-m/blink.c

clean:
	rm -rf $(BUILD)
