# Third-party dependency record

This repository does not redistribute N64 game data, Nintendo SDK files, proprietary IDO binaries, local language-model weights, or the third-party source repositories listed below. Build and workflow scripts acquire or connect to them separately.

| Component | Locked revision/version | Purpose | Declared license | Verification source |
|---|---|---|---|---|
| N64Recomp | `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` | Static recompilation | MIT | Upstream `LICENSE` |
| Splat (`splat64[mips]`) | `0.41.0` | N64 binary splitting and metadata generation | MIT | PyPI project metadata |
| RT64 | `f0728a2520d5aa735886240de3fee75cc805f6d6` | Native-port graphics renderer integration target | MIT | Upstream repository license |
| vcpkg baseline | `cd61e1e26a038e82d6550a3ebbe0fbbfe7da78e3` | C/C++ dependency resolution | MIT | Upstream repository license |
| RmlUi | Resolved by the locked vcpkg baseline, `svg` feature required | Launcher/menu UI | MIT | Upstream `LICENSE.txt` |
| LunaSVG | Resolved by the locked vcpkg baseline | SVG rendering used by RmlUi SVG support | MIT | Upstream `LICENSE` |
| FreeType | Resolved by the locked vcpkg baseline | Font rendering used by RmlUi | FTL or GPL-2.0-only | Upstream FreeType license documentation |
| SDL2 | Resolved by the locked vcpkg baseline | Window and event-loop scaffold | Zlib | Upstream SDL documentation |
| tomlkit | `0.13.3` | Structure-preserving TOML edits | MIT | PyPI project metadata |
| ruamel.yaml | `0.18.17` | Structure-preserving YAML edits | MIT | PyPI project metadata |
| setuptools | `82.0.1` | Python wheel build backend | MIT | Installed release metadata |
| Mupen64MCP | `9fa441d4c603efc47b570d021c767f93b6625cbd` reference only | Optional emulator/debug MCP workflow | MIT | Upstream README license section |
| LM Studio | Operator-installed | Optional local OpenAI-compatible server | See vendor terms | Official LM Studio documentation |
| llama.cpp | Operator-installed | Optional local OpenAI-compatible server | MIT | Upstream repository |

`dependencies.lock.json` is the machine-readable revision record. `sbom.spdx.json` describes the shipped Python package and its direct dependencies. vcpkg creates its own resolved dependency state during a runtime starter build.
