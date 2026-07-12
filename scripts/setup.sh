#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN is not available on PATH." >&2
  exit 1
fi

install_tkinter_if_possible() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Tkinter check: automatic install is only supported for Linux package managers."
    return
  fi

  local install_cmd=""
  if command -v apt-get >/dev/null 2>&1; then
    install_cmd="apt-get update && apt-get install -y python3-tk"
  elif command -v dnf >/dev/null 2>&1; then
    install_cmd="dnf install -y python3-tkinter"
  elif command -v yum >/dev/null 2>&1; then
    install_cmd="yum install -y python3-tkinter"
  elif command -v pacman >/dev/null 2>&1; then
    install_cmd="pacman -Sy --noconfirm tk"
  fi

  if [[ -z "$install_cmd" ]]; then
    echo "Tkinter check: no supported package manager found. Install Tkinter manually." >&2
    return
  fi

  echo "Tkinter is missing. Attempting to install system package..."
  if command -v sudo >/dev/null 2>&1; then
    sudo bash -lc "$install_cmd"
  elif [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    bash -lc "$install_cmd"
  else
    echo "Cannot install Tkinter automatically (no sudo/root)." >&2
    echo "Run this manually: $install_cmd" >&2
    exit 1
  fi
}

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  install_tkinter_if_possible
fi

"$PYTHON_BIN" -m pip install -r requirements.txt

"$PYTHON_BIN" - <<'PY'
import tkinter
print("Setup complete: tkinter is available.")
PY
