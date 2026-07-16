param(
  [Parameter(Mandatory=$true)][string]$SplatYaml,
  [Parameter(Mandatory=$true)][string]$AsmDir,
  [Parameter(Mandatory=$true)][string]$RecompToml,
  [string]$SymbolsDir = "symbols/recomp",
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
python -m n64recomp_kit scan-unsupported --asm-dir $AsmDir --out-dir $SymbolsDir
if ($DryRun) {
  python -m n64recomp_kit sync-ignored --config $RecompToml --ignored (Join-Path $SymbolsDir "ignored-genuine.txt") --dry-run
  python -m n64recomp_kit mips-link-preflight --config $SplatYaml
} else {
  python -m n64recomp_kit sync-ignored --config $RecompToml --ignored (Join-Path $SymbolsDir "ignored-genuine.txt")
  python -m n64recomp_kit mips-link-preflight --config $SplatYaml --execute
}
