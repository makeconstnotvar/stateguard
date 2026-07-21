#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

if [ -f "$KIT_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$KIT_ROOT/.venv/bin/activate"
fi

exec stateguard --repo "$KIT_ROOT/examples/order-workflow" run-cycle "$@"
