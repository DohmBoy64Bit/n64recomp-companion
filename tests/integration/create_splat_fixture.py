from pathlib import Path
import struct
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build/splat-integration").resolve()
root.mkdir(parents=True, exist_ok=True)
rom = bytearray(0x2000)
rom[0:4] = bytes.fromhex("80371240")
rom[8:12] = struct.pack(">I", 0x80000400)
rom[0x20:0x20 + len(b"STARFALL FIXTURE")] = b"STARFALL FIXTURE"
(root / "minimal.z64").write_bytes(rom)
(root / "splat.yaml").write_text('''options:
  base_path: "."
  platform: n64
  compiler: "IDO"
  basename: "minimal"
  target_path: "minimal.z64"
  asm_path: "asm"
  build_path: "build"
  ld_script_path: "minimal.ld"
  cache_path: ".splache"
  symbol_addrs_path: "symbol_addrs.txt"
  undefined_funcs_auto_path: "undefined_funcs_auto.txt"
  undefined_syms_auto_path: "undefined_syms_auto.txt"
segments:
  - name: header
    type: header
    start: 0x0
  - name: body
    type: bin
    start: 0x40
  - [0x2000]
''', encoding="utf-8")
print(root / "splat.yaml")
