#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-build/n64recomp-integration}"
N64RECOMP_BIN="${2:?pass N64Recomp executable path}"
mkdir -p "$ROOT/asm" "$ROOT/build"
cat > "$ROOT/asm/entry.s" <<'ASM'
.set noreorder
.set noat
.section .text
.globl entry
.type entry, @function
entry:
    jr $ra
    nop
.size entry, .-entry
ASM
cat > "$ROOT/synthetic.ld" <<'LD'
OUTPUT_ARCH(mips)
ENTRY(entry)
SECTIONS {
  . = 0x80000400;
  .text : { *(.text*) }
  .data : { *(.data*) }
  .rodata : { *(.rodata*) }
  .bss : { *(.bss*) *(COMMON) }
}
LD
mips-linux-gnu-as -EB -mips3 -o "$ROOT/build/entry.o" "$ROOT/asm/entry.s"
mips-linux-gnu-ld -T "$ROOT/synthetic.ld" -o "$ROOT/build/synthetic.elf" "$ROOT/build/entry.o"
cat > "$ROOT/synthetic.toml" <<EOF2
[input]
entrypoint = 0x80000400
elf_path = "build/synthetic.elf"
output_func_path = "RecompiledFuncs"
EOF2
(
  cd "$ROOT"
  "$N64RECOMP_BIN" synthetic.toml
)
test -d "$ROOT/RecompiledFuncs"
find "$ROOT/RecompiledFuncs" -type f | grep -q .
