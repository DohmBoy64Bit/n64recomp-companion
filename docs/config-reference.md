# N64Recomp TOML config reference used by the checker

This checker is intentionally conservative: it validates fields confirmed by the upstream config parser and warns or errors on values that would fail later.

## Required shape

```toml
[input]
entrypoint = 0x80000400
elf_path = "game.elf"
output_func_path = "RecompiledFuncs"

[patches]
stubs = []
ignored = []
renamed = []
```

`entrypoint` is optional in upstream parsing but is strongly useful for most projects. `output_func_path` is required by upstream parsing. Provide either `elf_path`, or both `symbols_file_path` and `rom_file_path`.

## `[input]` fields

| Field | Type | Checker behavior |
|---|---:|---|
| `entrypoint` | integer | Must be word-aligned when present. |
| `elf_path` | string | Checked for existence unless `--allow-missing-paths` is used. |
| `symbols_file_path` | string | Checked for existence unless `--allow-missing-paths` is used. |
| `rom_file_path` | string | Checked for existence unless `--allow-missing-paths` is used. |
| `output_func_path` | string | Required; may be created by `run`. |
| `relocatable_sections_path` | string | Checked for existence when present. |
| `uses_mips3_float_mode` | bool | Type checked. |
| `bss_section_suffix` | string | Type checked. |
| `single_file_output` | bool | Type checked. |
| `use_absolute_symbols` | bool | Type checked. |
| `output_binary_path` | string | Checked for existence when present. |
| `unpaired_lo16_warnings` | bool | Type checked. |
| `use_mdebug` | bool | Type checked. |
| `recomp_include` | string | Type checked. |
| `functions_per_output_file` | integer | Must be greater than zero. |
| `trace_mode` | bool | Type checked. |
| `func_reference_syms_file` | string | Valid only in ELF mode. |
| `data_reference_syms_files` | array of strings | Requires `func_reference_syms_file`. |
| `allow_exports` | bool | Type checked. |
| `strict_patch_mode` | bool | Type checked. |

## Manual functions

```toml
[[input.manual_funcs]]
name = "Manual_Function"
section = ".text"
vram = 0x80010000
size = 0x40
```

Each manual function requires `name`, `section`, `vram`, and `size`. `vram` must be word-aligned and `size` must be a positive multiple of 4.

## Manual function sizes

```toml
[[input.function_sizes]]
name = "Known_Function"
size = 0x80
```

`size` must be a positive multiple of 4.

## Patches

```toml
[patches]
stubs = ["Function_To_Stub"]
ignored = ["Non_Function_Symbol"]
renamed = ["Old_Name"]

[[patches.instruction]]
func = "Function_Name"
vram = 0x80012000
value = 0x00000000

[[patches.hook]]
func = "Function_Name"
before_vram = 0x80012010
text = "custom_hook(rdram, ctx);"
```

Instruction patch `vram` and hook `before_vram` must be word-aligned. Hook `before_vram` is optional.


## `mdebug_file_mappings`

Current N64Recomp accepts an array of mapping tables under `[input]`. The checker requires non-empty `filename`, `input_section`, and `output_section` strings. `input_section` is constrained to the section names accepted by the current upstream parser path used by this package: `.text`, `.data`, `.rodata`, or `.bss`.

```toml
[[input.mdebug_file_mappings]]
filename = "src/boot.c"
input_section = ".text"
output_section = ".text"
```

Unknown `[input]` keys produce warnings rather than errors. This catches misspellings while retaining forward compatibility with newer upstream fields.
