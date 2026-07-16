# Local LLM + Mupen64MCP workflow

This optional workflow connects Mupen64MCP to an OpenAI-compatible local server from LM Studio or llama.cpp. The bridge starts in **read-only mode**: controller input, lifecycle/debug control, unknown tools, and memory writes are denied unless the operator explicitly changes the mutation policy.

## Generate the workflow files

The release already includes these files. Run the generator when adding the workflow to another project or restoring a deleted script:

```powershell
python -m n64recomp_kit emit-local-llm-workflow --root . --overwrite
```

## Configure the Mupen64MCP checkout

```powershell
$env:MUPEN64MCP_ROOT = 'C:\dev\Mupen64MCP'
```

The generated MCP client config references that environment variable rather than a machine-specific drive path.

## Start the daemon

Rendered mode uses Rice video and RSP-HLE for framebuffer evidence:

```powershell
.\scripts\Start-Mupen64McpDaemon.ps1 -Rom C:\roms\starfall_us.z64 -Mode Rendered
```

Headless mode keeps CPU/debug tooling available with dummy graphics:

```powershell
.\scripts\Start-Mupen64McpDaemon.ps1 -Rom C:\roms\starfall_us.z64 -Mode Headless
```

Do not pass `-AllowWriteMemory` for normal analysis. That daemon switch should only be enabled for an intentional write session.

## Start the MCP server

```powershell
.\scripts\Start-Mupen64McpServer.ps1
```

## Verify the local model before exposing tools

Start LM Studio from its Developer tab or run:

```powershell
.\scripts\Start-LMStudioServer.ps1 -StartWithLmsCli
```

For llama.cpp, start either supported server mode:

```powershell
.\scripts\Start-LlamaCppServer.ps1 -Mode llama-cpp-python -Model C:\models\model.gguf
```

First send a no-tools request. Then run the tool-call capability probe in `local-llm-doctor` by providing a model. A model/server combination that does not return OpenAI-style `tool_calls` is unsuitable for the MCP agent loop even when ordinary chat works.

## Run a read-only MCP prompt

```powershell
$ModelId = (Invoke-RestMethod http://127.0.0.1:1234/v1/models).data[0].id
.\scripts\Invoke-LocalLlmMcpPrompt.ps1 -Provider LMStudio -Model $ModelId -MupenRoot $env:MUPEN64MCP_ROOT -Prompt 'Read status, PC, and registers. Do not change emulator state.'
```

The equivalent direct CLI command is:

```powershell
python -m n64recomp_kit local-llm-ask --provider lmstudio --model $ModelId --mupen-root $env:MUPEN64MCP_ROOT --prompt 'Read status, PC, and registers without changing emulator state.'
```

The default `-MutationPolicy deny` exposes read-only tools and denies mutations. `prompt` asks for confirmation in an interactive terminal. `allow` is an explicit noninteractive override. `-AllowTool` can further restrict the exposed names.

```powershell
.\scripts\Invoke-LocalLlmMcpPrompt.ps1 -Provider LMStudio -Model $ModelId -MupenRoot $env:MUPEN64MCP_ROOT -MutationPolicy prompt -AllowTool n64_get_status,n64_get_pc,n64_get_registers,n64_set_controller -Prompt 'Inspect boot state and ask before pressing START.'
```

## Diagnostics

```powershell
.\scripts\Test-LocalLlmMcpWorkflow.ps1 -MupenRoot $env:MUPEN64MCP_ROOT
python -m n64recomp_kit local-llm-doctor --mupen-root $env:MUPEN64MCP_ROOT --model $ModelId --json
python -m n64recomp_kit local-llm-doctor --mupen-root $env:MUPEN64MCP_ROOT --skip-server-probes --json
```

## Operational boundaries

- Real Rice video and RSP-HLE are needed when framebuffer capture must contain rendered pixels.
- Dummy graphics is acceptable for CPU-oriented debugging but can produce a black framebuffer.
- Keep ROM files outside the repository.
- Record every mutation and the evidence that justified it.
- Prefer a fresh emulator state before comparing traces from two code changes.
