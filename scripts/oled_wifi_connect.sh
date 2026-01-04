#!/usr/bin/env bash
set -euo pipefail

SSID="${WIFI_SSID:-}"
PSK="${WIFI_PSK:-}"

if [[ -z "${SSID}" ]]; then
  echo "WIFI_SSID is required." >&2
  exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
  echo "nmcli not found; cannot configure Wi-Fi." >&2
  exit 1
fi

if [[ -n "${PSK}" ]]; then
  nmcli dev wifi connect "${SSID}" password "${PSK}"
else
  nmcli dev wifi connect "${SSID}"
fi
