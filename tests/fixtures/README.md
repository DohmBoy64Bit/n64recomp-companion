# Test fixtures

These files are tiny synthetic fixtures used by the unit tests only.

- `minimal.z64` is a 4 KiB synthetic N64-style header image with the standard byte-order magic and test metadata. It is not a game ROM.
- `minimal.v64` is the same synthetic image byte-swapped for converter tests.
- `minimal_mips_be.elf` is a tiny ELF32 big-endian MIPS fixture with one executable `.text` section.

`tests/fixture_support.py` can regenerate these files if they are omitted by an archive or ignored by a VCS workflow.
