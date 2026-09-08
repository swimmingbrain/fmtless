# The same eight log lines built both ways for a Cortex-M4, linked with
# newlib-nano, so the difference can be measured rather than argued about.

CROSS   ?= arm-none-eabi-
FLAGS    = -mcpu=cortex-m4 -mthumb -std=c11 -Os -Wall -Wextra \
           -ffunction-sections -fdata-sections -I../../include
LINK     = -specs=nano.specs -specs=nosys.specs -Wl,--gc-sections \
           -Wl,-Ttext=0x8000 -nostartfiles -Wl,-e,main

.PHONY: compare clean

compare:
	@echo "                                       flash"
	@for variant in "fmtless:" "printf:-DUSE_PRINTF=1"; do \
	    name=$${variant%%:*}; defs=$${variant#*:}; \
	    $(CROSS)gcc $(FLAGS) $$defs -c -o blink_$$name.o blink.c; \
	    $(CROSS)gcc $(FLAGS) $$defs -c -o fw_$$name.o firmware.c; \
	    $(CROSS)gcc $(FLAGS) $(LINK) -o $$name.elf blink_$$name.o fw_$$name.o 2>/dev/null; \
	    $(CROSS)objcopy -O binary $$name.elf $$name.bin; \
	    printf "%-38s %7d\n" "$$name" $$(wc -c < $$name.bin); \
	done 2>/dev/null
	@echo
	@printf "log text found inside the fmtless image: %s\n" \
	    "$$(strings fmtless.bin | grep -c 'did not answer' || true)"
	@printf "catalog carried by the fmtless ELF:      %s bytes\n" \
	    "$$($(CROSS)size -A fmtless.elf | awk '/^fmtless /{print $$2}')"
	@rm -f *.o *.elf *.bin

clean:
	rm -f *.o *.elf *.bin
