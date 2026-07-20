#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Host preparation is only required on Linux." >&2
  exit 0
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 2
fi

sysctl -w vm.max_map_count=524288
sysctl -w fs.file-max=131072

cat <<'MSG'
Host kernel limits were updated for the current boot.
Persist them through your configuration-management system, for example:

  vm.max_map_count=524288
  fs.file-max=131072

Do not manage production hosts by repeatedly editing them by hand.
MSG
