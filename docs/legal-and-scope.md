# Legal and scope notes

This repository is a lawful workflow toolkit. It does not contain ROMs, game assets, proprietary Nintendo SDK files, private compiler binaries, or commercial-game runtime code.

## Acceptable inputs

- Hashes, tool logs, command output, crash stacks, and trace summaries.
- User-owned local paths during a private session.
- Splat YAML, N64Recomp TOML, linker scripts, and symbol files that the project is allowed to share.
- Small assembly snippets needed to diagnose boundaries or delay slots.

## Material not to commit

- `.z64`, `.n64`, `.v64`, `.rom`, `.bin` baseroms or extracted game assets.
- Proprietary compiler binaries and SDK headers/libraries.
- Generated output that contains copyrighted game code when the project license does not allow redistribution.
- Local absolute ROM paths or private trace logs from unreleased projects.

## Scope boundary

The toolkit improves setup, validation, reports, and evidence discipline. It does not turn an arbitrary ROM into a complete playable Windows port. That requires project-specific metadata and runtime integration.
