#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-${REPO_ROOT}/config.toml}"

export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

if command -v libcamerify >/dev/null 2>&1 && [[ "${DMC_USE_LIBCAMERIFY:-1}" == "1" ]]; then
  exec libcamerify python3 -m dmc_ai_mobility.app.cli robot --config "${CONFIG_PATH}" "${@:2}"
else
  exec python3 -m dmc_ai_mobility.app.cli robot --config "${CONFIG_PATH}" "${@:2}"
fi
