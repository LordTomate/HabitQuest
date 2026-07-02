#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${HQ_ENV_NAME:-habitquest}"

if ! command -v conda >/dev/null 2>&1; then
  echo "Error: conda is not installed or not on PATH." >&2
  exit 1
fi

# Initialize conda for this shell session.
eval "$(conda shell.bash hook)"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda env update -n "$ENV_NAME" -f environment.yaml --prune
else
  conda env create -n "$ENV_NAME" -f environment.yaml
fi

conda activate "$ENV_NAME"

python - <<'PY'
import tkinter
print("Conda setup complete: tkinter is available.")
PY
