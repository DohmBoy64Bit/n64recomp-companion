SHELL := pwsh.exe
.PHONY: configure build run clean

configure:
	./scripts/Configure-Windows.ps1

build:
	./scripts/Build-Windows.ps1

run:
	./scripts/Run-Windows.ps1

clean:
	Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
