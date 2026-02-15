#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Best-effort OLED blank before poweroff
PYTHONPATH="$REPO_ROOT/src:${PYTHONPATH:-}" python3 - <<'PY' || true
try:
    from dmc_ai_mobility.drivers.oled import Ssd1306OledConfig, Ssd1306OledDriver
    o = Ssd1306OledDriver(Ssd1306OledConfig())
    o.close()  # fill(0)+show()
except Exception:
    pass
PY

# Give I2C write a short moment to flush
sleep 0.2

if command -v systemctl >/dev/null 2>&1; then
  exec systemctl poweroff
fi

exec /sbin/poweroff
