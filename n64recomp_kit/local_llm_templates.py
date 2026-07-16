from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .openai_compat import DEFAULT_LLAMA_CPP_BASE_URL, DEFAULT_LMSTUDIO_BASE_URL
from .util import atomic_write_text, write_json

DEFAULT_MCP_SERVER_NAME = "n64-debug-mcp"

@dataclass
class LocalLlmWorkflowReport:
    root: str
    files: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

START_DAEMON_PS1 = '<#\nStarts the Mupen64MCP native daemon on Windows.\nReal Rice + RSP-HLE plugins are selected in Rendered mode so framebuffer tools can capture pixels.\nDummy graphics remains available for CPU/debug sessions where a black framebuffer is acceptable.\n#>\n[CmdletBinding()]\nparam(\n  [string]$MupenRoot = $env:MUPEN64MCP_ROOT,\n  [Parameter(Mandatory=$true)][string]$Rom,\n  [ValidateSet(\'Rendered\',\'Headless\')][string]$Mode = \'Rendered\',\n  [int]$Port = 9876,\n  [switch]$AllowWriteMemory,\n  [string]$DaemonExe,\n  [string]$Core,\n  [string]$DataDir,\n  [string]$ConfigDir,\n  [string]$Gfx,\n  [string]$Rsp,\n  [string]$Audio = \'dummy\',\n  [string]$InputPlugin,\n  [string]$Msys2Bin = \'C:\\msys64\\mingw64\\bin\',\n  [string]$WinLibsBin = \'\',\n  [switch]$NoStopExisting\n)\n\n$ErrorActionPreference = \'Stop\'\n$rootInput = $MupenRoot\nif (-not $rootInput) { throw \'Pass -MupenRoot or set MUPEN64MCP_ROOT.\' }\n$root = (Resolve-Path -LiteralPath $rootInput).Path\nif (-not $DaemonExe) { $DaemonExe = Join-Path $root \'native\\n64_debug_daemon\\build\\n64-debug-daemon.exe\' }\nif (-not $Core) { $Core = Join-Path $root \'build\\mupen64plus\\lib\\mupen64plus.dll\' }\nif (-not $DataDir) { $DataDir = Join-Path $root \'build\\mupen64plus\\share\' }\nif (-not $ConfigDir) { $ConfigDir = Join-Path $root \'build\\mupen64plus\\config\' }\nif (-not $InputPlugin) { $InputPlugin = Join-Path $root \'native\\n64_debug_daemon\\build\\mupen64plus-input-inject.dll\' }\nif (-not $Gfx) {\n  if ($Mode -eq \'Rendered\') { $Gfx = Join-Path $root \'plugins\\mupen64plus-video-rice.dll\' } else { $Gfx = \'dummy\' }\n}\nif (-not $Rsp) {\n  if ($Mode -eq \'Rendered\') { $Rsp = Join-Path $root \'plugins\\mupen64plus-rsp-hle.dll\' } else { $Rsp = \'dummy\' }\n}\n\n$required = @($DaemonExe, $Core, $Rom, $DataDir, $ConfigDir, $InputPlugin)\nif ($Gfx -ne \'dummy\') { $required += $Gfx }\nif ($Rsp -ne \'dummy\') { $required += $Rsp }\nforeach ($path in $required) {\n  if (-not (Test-Path -LiteralPath $path)) { throw "Required path not found: $path" }\n}\n\n# PATH ORDER CRITICAL for this workflow: MSYS2 -> WinLibs -> Mupen64Plus core lib -> existing system PATH.\n$pathParts = @()\nif ($Msys2Bin -and (Test-Path -LiteralPath $Msys2Bin)) { $pathParts += $Msys2Bin }\nif ($WinLibsBin -and (Test-Path -LiteralPath $WinLibsBin)) { $pathParts += $WinLibsBin }\n$pathParts += (Split-Path -Parent $Core)\n$env:Path = (($pathParts + @($env:Path)) -join \';\')\n\nif (-not $NoStopExisting) {\n  Get-Process \'n64-debug-daemon\' -ErrorAction SilentlyContinue | Stop-Process -Force\n  Start-Sleep -Seconds 1\n}\n\n$argsList = @(\n  \'--core\', $Core,\n  \'--rom\', $Rom,\n  \'--datadir\', $DataDir,\n  \'--configdir\', $ConfigDir,\n  \'--gfx\', $Gfx,\n  \'--rsp\', $Rsp,\n  \'--audio\', $Audio,\n  \'--input\', $InputPlugin,\n  \'--port\', [string]$Port\n)\nif ($AllowWriteMemory) { $argsList += \'--allow-write-memory\' }\n\nWrite-Host "Starting n64-debug-daemon on port $Port"\nWrite-Host "Mode: $Mode"\nif ($Mode -eq \'Rendered\') {\n  Write-Host \'Rendered mode uses real Rice video and RSP-HLE plugins so framebuffer capture can return pixels.\'\n}\nStart-Process -FilePath $DaemonExe -ArgumentList $argsList -NoNewWindow\nWrite-Host \'Daemon launch requested.\'\nWrite-Host \'For games that need START on boot, call the MCP tool n64_set_controller with buttons="START" and sticky=true before resume.\'\n'

START_MCP_SERVER_PS1 = '<#\nStarts the Python Mupen64MCP server from the repository checkout.\n#>\n[CmdletBinding()]\nparam(\n  [string]$MupenRoot = $env:MUPEN64MCP_ROOT,\n  [switch]$UseInstalledCommand\n)\n$ErrorActionPreference = \'Stop\'\n$rootInput = $MupenRoot\nif (-not $rootInput) { throw \'Pass -MupenRoot or set MUPEN64MCP_ROOT.\' }\n$mcpPython = Join-Path (Resolve-Path -LiteralPath $rootInput).Path \'mcp\\python\'\nif (-not (Test-Path -LiteralPath $mcpPython)) { throw "Mupen64MCP Python server directory not found: $mcpPython" }\nif ($UseInstalledCommand) {\n  $cmd = Get-Command \'n64-debug-mcp\' -ErrorAction Stop\n  & $cmd.Source\n  exit $LASTEXITCODE\n}\n$uv = Get-Command \'uv\' -ErrorAction SilentlyContinue\nif ($uv) {\n  & $uv.Source --directory $mcpPython run n64-debug-mcp\n  exit $LASTEXITCODE\n}\nPush-Location $mcpPython\ntry {\n  python -m pip install -e .\n  n64-debug-mcp\n  exit $LASTEXITCODE\n}\nfinally { Pop-Location }\n'

START_LMSTUDIO_PS1 = '<#\nStarts or verifies the LM Studio local API server.\nLM Studio can also be started from the app Developer tab.\n#>\n[CmdletBinding()]\nparam(\n  [string]$BaseUrl = \'http://127.0.0.1:1234/v1\',\n  [switch]$StartWithLmsCli,\n  [switch]$VerifyOnly\n)\n$ErrorActionPreference = \'Stop\'\nif ($StartWithLmsCli -and -not $VerifyOnly) {\n  $lms = Get-Command \'lms\' -ErrorAction SilentlyContinue\n  if (-not $lms) { throw \'LM Studio CLI `lms` was not found on PATH. Start the server from the LM Studio Developer tab or install/enable the CLI.\' }\n  & $lms.Source server start\n}\n$modelsUrl = ($BaseUrl.TrimEnd(\'/\')) + \'/models\'\ntry {\n  $models = Invoke-RestMethod -Uri $modelsUrl -Headers @{ Authorization = \'Bearer lm-studio\' } -TimeoutSec 5\n  Write-Host "LM Studio API reachable at $BaseUrl"\n  if ($models.data) { $models.data | Select-Object -First 20 id | Format-Table -AutoSize }\n}\ncatch {\n  throw "LM Studio API not reachable at $BaseUrl. Start it from the Developer tab, or run this script with -StartWithLmsCli if lms is installed. $($_.Exception.Message)"\n}\n'

START_LLAMA_CPP_PS1 = '<#\nStarts a local OpenAI-compatible llama.cpp server using either llama-cpp-python or llama-server.\n#>\n[CmdletBinding()]\nparam(\n  [Parameter(Mandatory=$true)][string]$Model,\n  [ValidateSet(\'llama-cpp-python\',\'llama-server\')][string]$Mode = \'llama-cpp-python\',\n  [string]$HostAddress = \'127.0.0.1\',\n  [int]$Port = 8080,\n  [int]$ContextSize = 8192,\n  [string]$ServerExe,\n  [switch]$NoNewWindow\n)\n$ErrorActionPreference = \'Stop\'\nif (-not (Test-Path -LiteralPath $Model)) { throw "Model file not found: $Model" }\nif ($Mode -eq \'llama-cpp-python\') {\n  $python = Get-Command \'python\' -ErrorAction Stop\n  $argsList = @(\'-m\',\'llama_cpp.server\',\'--model\',$Model,\'--host\',$HostAddress,\'--port\',[string]$Port,\'--n_ctx\',[string]$ContextSize)\n  Write-Host "Starting llama-cpp-python server at http://$HostAddress`:$Port/v1"\n  Start-Process -FilePath $python.Source -ArgumentList $argsList -NoNewWindow:$NoNewWindow\n} else {\n  if (-not $ServerExe) {\n    $cmd = Get-Command \'llama-server\' -ErrorAction SilentlyContinue\n    if (-not $cmd) { throw \'llama-server was not found on PATH. Pass -ServerExe or use -Mode llama-cpp-python.\' }\n    $ServerExe = $cmd.Source\n  }\n  $argsList = @(\'--model\',$Model,\'--host\',$HostAddress,\'--port\',[string]$Port,\'--ctx-size\',[string]$ContextSize)\n  Write-Host "Starting llama-server at http://$HostAddress`:$Port/v1"\n  Start-Process -FilePath $ServerExe -ArgumentList $argsList -NoNewWindow:$NoNewWindow\n}\n'

INVOKE_LOCAL_LLM_MCP_PS1 = "<#\nRuns one local LLM prompt through n64recomp-kit. When -MupenRoot is supplied, the command also exposes Mupen64MCP tools to the model.\n#>\n[CmdletBinding()]\nparam(\n  [Parameter(Mandatory=$true)][string]$Prompt,\n  [Parameter(Mandatory=$true)][string]$Model,\n  [ValidateSet('LMStudio','LlamaCpp')][string]$Provider = 'LMStudio',\n  [string]$BaseUrl,\n  [string]$ApiKey = 'local',\n  [string]$MupenRoot,\n  [int]$MaxToolRounds = 8,\n  [ValidateSet('deny','prompt','allow')][string]$MutationPolicy = 'deny',\n  [string[]]$AllowTool = @()\n)\n$ErrorActionPreference = 'Stop'\nif (-not $BaseUrl) {\n  if ($Provider -eq 'LMStudio') { $BaseUrl = 'http://127.0.0.1:1234/v1'; $ApiKey = 'lm-studio' }\n  else { $BaseUrl = 'http://127.0.0.1:8080/v1' }\n}\n$providerArg = if ($Provider -eq 'LMStudio') { 'lmstudio' } else { 'llama-cpp' }\n$argsList = @('local-llm-ask','--prompt',$Prompt,'--model',$Model,'--provider',$providerArg,'--base-url',$BaseUrl,'--api-key',$ApiKey,'--max-tool-rounds',[string]$MaxToolRounds,'--mutation-policy',$MutationPolicy)\nforeach ($tool in $AllowTool) { $argsList += @('--allow-tool',$tool) }\nif ($MupenRoot) {\n  $argsList += @('--mupen-root',(Resolve-Path -LiteralPath $MupenRoot).Path)\n}\npython -m n64recomp_kit @argsList\nexit $LASTEXITCODE\n"

TEST_LOCAL_LLM_MCP_PS1 = "<#\nChecks script presence, optional Mupen64MCP paths, and optionally local OpenAI-compatible API endpoints.\n#>\n[CmdletBinding()]\nparam(\n  [string]$MupenRoot,\n  [string]$LMStudioBaseUrl = 'http://127.0.0.1:1234/v1',\n  [string]$LlamaCppBaseUrl = 'http://127.0.0.1:8080/v1',\n  [switch]$SkipServerProbes\n)\n$ErrorActionPreference = 'Stop'\n$argsList = @('local-llm-doctor','--lmstudio-base-url',$LMStudioBaseUrl,'--llama-cpp-base-url',$LlamaCppBaseUrl)\nif ($MupenRoot) { $argsList += @('--mupen-root',$MupenRoot) }\nif ($SkipServerProbes) { $argsList += '--skip-server-probes' }\npython -m n64recomp_kit @argsList\nexit $LASTEXITCODE\n"

MCP_ANALYSIS_PROMPT = '# N64 MCP analysis prompt\n\nYou are assisting a Windows-first N64Recomp workflow. Use Mupen64MCP tools conservatively and report every address, register value, breakpoint, and memory range you used as evidence.\n\nRecommended first steps:\n\n1. Check daemon status with `n64_get_status`.\n2. If the game is sitting at boot or attract mode, set START before resuming with `n64_set_controller` using `buttons` set to `START` and `sticky` set to true.\n3. Capture CPU state with `n64_get_pc` and `n64_get_registers`.\n4. Use breakpoints, traces, RDRAM reads, PI DMA capture, and framebuffer capture to connect runtime behavior back to Splat/N64Recomp symbols.\n5. Do not write memory unless the session explicitly allows it and the change is recorded.\n\nWhen framebuffer evidence is needed, the daemon should use real Rice video and RSP-HLE plugins. Dummy graphics is acceptable for CPU/debugging, but it can return a black framebuffer.\n'

LOCAL_LLM_DOC = "# Local LLM + Mupen64MCP workflow\n\nThis optional workflow connects Mupen64MCP to an OpenAI-compatible local server from LM Studio or llama.cpp. The bridge starts in **read-only mode**: controller input, lifecycle/debug control, unknown tools, and memory writes are denied unless the operator explicitly changes the mutation policy.\n\n## Configure the Mupen64MCP checkout\n\n```powershell\n$env:MUPEN64MCP_ROOT = 'C:\\dev\\Mupen64MCP'\n```\n\nThe generated MCP client config references that environment variable rather than a machine-specific drive path.\n\n## Start the daemon\n\nRendered mode uses Rice video and RSP-HLE for framebuffer evidence:\n\n```powershell\n.\\scripts\\Start-Mupen64McpDaemon.ps1 -Rom C:\\roms\\starfall_us.z64 -Mode Rendered\n```\n\nHeadless mode keeps CPU/debug tooling available with dummy graphics:\n\n```powershell\n.\\scripts\\Start-Mupen64McpDaemon.ps1 -Rom C:\\roms\\starfall_us.z64 -Mode Headless\n```\n\nDo not pass `-AllowWriteMemory` for normal analysis. That daemon switch should only be enabled for an intentional write session.\n\n## Start the MCP server\n\n```powershell\n.\\scripts\\Start-Mupen64McpServer.ps1\n```\n\n## Verify the local model before exposing tools\n\nStart LM Studio from its Developer tab or run:\n\n```powershell\n.\\scripts\\Start-LMStudioServer.ps1 -StartWithLmsCli\n```\n\nFor llama.cpp, start either supported server mode:\n\n```powershell\n.\\scripts\\Start-LlamaCppServer.ps1 -Mode llama-cpp-python -Model C:\\models\\model.gguf\n```\n\nFirst send a no-tools request. Then run the tool-call capability probe in `local-llm-doctor` by providing a model. A model/server combination that does not return OpenAI-style `tool_calls` is unsuitable for the MCP agent loop even when ordinary chat works.\n\n## Run a read-only MCP prompt\n\n```powershell\n$ModelId = (Invoke-RestMethod http://127.0.0.1:1234/v1/models).data[0].id\n.\\scripts\\Invoke-LocalLlmMcpPrompt.ps1 -Provider LMStudio -Model $ModelId -MupenRoot $env:MUPEN64MCP_ROOT -Prompt 'Read status, PC, and registers. Do not change emulator state.'\n```\n\nEquivalent direct CLI:\n\n```powershell\npython -m n64recomp_kit local-llm-ask --provider lmstudio --model $ModelId --mupen-root $env:MUPEN64MCP_ROOT --prompt 'Read status, PC, and registers without changing emulator state.'\n```\n\nThe default `-MutationPolicy deny` exposes read-only tools and denies mutations. `prompt` asks for confirmation in an interactive terminal. `allow` is an explicit noninteractive override. `-AllowTool` can further restrict the exposed names.\n\n```powershell\n.\\scripts\\Invoke-LocalLlmMcpPrompt.ps1 -Provider LMStudio -Model $ModelId -MupenRoot $env:MUPEN64MCP_ROOT -MutationPolicy prompt -AllowTool n64_get_status,n64_get_pc,n64_get_registers,n64_set_controller -Prompt 'Inspect boot state and ask before pressing START.'\n```\n\n## Diagnostics\n\n```powershell\n.\\scripts\\Test-LocalLlmMcpWorkflow.ps1 -MupenRoot $env:MUPEN64MCP_ROOT\npython -m n64recomp_kit local-llm-doctor --mupen-root $env:MUPEN64MCP_ROOT --model $ModelId --json\npython -m n64recomp_kit local-llm-doctor --mupen-root $env:MUPEN64MCP_ROOT --skip-server-probes --json\n```\n\n## Operational boundaries\n\n- Real Rice video and RSP-HLE are needed when framebuffer capture must contain rendered pixels.\n- Dummy graphics is acceptable for CPU-oriented debugging but can produce a black framebuffer.\n- Keep ROM files outside the repository.\n- Record every mutation and the evidence that justified it.\n- Prefer a fresh emulator state before comparing traces from two code changes.\n"

def _write(path: Path, text: str, *, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = text.replace("\n", "\r\n") if path.suffix.lower() == ".ps1" else text
    atomic_write_text(path, rendered)
    return str(path)


def _mcp_client_config(server_name: str = DEFAULT_MCP_SERVER_NAME) -> dict[str, Any]:
    return {
        "mcpServers": {
            server_name: {
                "command": "powershell",
                "args": ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/Start-Mupen64McpServer.ps1"],
                "env": {"MUPEN64MCP_ROOT": "${MUPEN64MCP_ROOT}"},
            }
        }
    }


def emit_local_llm_workflow(root: str | Path = ".", *, mupen_root: str | None = None, overwrite: bool = False) -> LocalLlmWorkflowReport:
    root_path = Path(root)
    files: list[str] = []
    scripts = root_path / "scripts"
    configs = root_path / "configs" / "local-llm"
    prompts = root_path / "prompts"
    docs = root_path / "docs"
    for name, content in [
        ("Start-Mupen64McpDaemon.ps1", START_DAEMON_PS1),
        ("Start-Mupen64McpServer.ps1", START_MCP_SERVER_PS1),
        ("Start-LMStudioServer.ps1", START_LMSTUDIO_PS1),
        ("Start-LlamaCppServer.ps1", START_LLAMA_CPP_PS1),
        ("Invoke-LocalLlmMcpPrompt.ps1", INVOKE_LOCAL_LLM_MCP_PS1),
        ("Test-LocalLlmMcpWorkflow.ps1", TEST_LOCAL_LLM_MCP_PS1),
    ]:
        files.append(_write(scripts / name, content, overwrite=overwrite))
    payloads = [
        (configs / "mcp-client-config.json", _mcp_client_config()),
        (configs / "local-agent.json", {
            "lmstudio": {"base_url": DEFAULT_LMSTUDIO_BASE_URL, "api_key": "lm-studio"},
            "llama_cpp": {"base_url": DEFAULT_LLAMA_CPP_BASE_URL, "api_key": "local"},
            "mcp": {
                "server_name": DEFAULT_MCP_SERVER_NAME,
                "command": "powershell",
                "args": ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/Start-Mupen64McpServer.ps1"],
                "root_env": "MUPEN64MCP_ROOT",
            },
            "policy": {"mutation_policy": "deny", "allowed_tools": []},
            "daemon": {
                "port": 9876,
                "rendered_capture": {"gfx": "plugins/mupen64plus-video-rice.dll", "rsp": "plugins/mupen64plus-rsp-hle.dll", "audio": "dummy"},
                "headless_debug": {"gfx": "dummy", "rsp": "dummy", "audio": "dummy"},
            },
        }),
    ]
    for path, payload in payloads:
        if path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing file: {path}")
        write_json(path, payload)
        files.append(str(path))
    if mupen_root:
        files.append(_write(configs / "mupen-root.ps1", f"$env:MUPEN64MCP_ROOT = {json.dumps(str(Path(mupen_root)))}\n", overwrite=overwrite))
    files.append(_write(prompts / "n64-mcp-analysis.md", MCP_ANALYSIS_PROMPT, overwrite=overwrite))
    files.append(_write(docs / "local-llm-mcp.md", LOCAL_LLM_DOC, overwrite=overwrite))
    return LocalLlmWorkflowReport(root=str(root_path), files=files)
