#!/usr/bin/env bash
set -euo pipefail

PREFIX="$PWD/.deps/decomp-tools"
PYTHON_BIN="${PYTHON:-python3}"
INSTALL_APT_MIPS=0

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap_decomp_tools.sh [--prefix PATH] [--python PYTHON] [--install-apt-mips]

Installs the Python Splat toolchain into a local virtual environment.
With --install-apt-mips on Debian/Ubuntu, it also installs open GNU MIPS tools:
  binutils-mips-linux-gnu gcc-mips-linux-gnu
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --install-apt-mips) INSTALL_APT_MIPS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$INSTALL_APT_MIPS" -eq 1 ]; then
  if command -v apt-get >/dev/null 2>&1; then
    SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
      SUDO="sudo"
    fi
    $SUDO apt-get update
    $SUDO apt-get install -y --no-install-recommends binutils-mips-linux-gnu gcc-mips-linux-gnu
  else
    echo "--install-apt-mips currently supports Debian/Ubuntu apt-get systems only." >&2
    exit 1
  fi
fi

mkdir -p "$PREFIX"
"$PYTHON_BIN" -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/python" -m pip install --upgrade pip
"$PREFIX/venv/bin/python" -m pip install -r requirements-decomp.txt
cat > "$PREFIX/env.sh" <<EOF
export PATH="$PREFIX/venv/bin:\$PATH"
EOF

echo "Installed Splat environment at $PREFIX"
echo "Run: source $PREFIX/env.sh"
