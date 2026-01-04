#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

TARGET_BRANCH="${TARGET_BRANCH:-}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"
SERVICE_NAME="${SERVICE_NAME:-dmc-ai-mobility.service}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"
SUDO="${SUDO:-}"

if [[ -z "${TARGET_BRANCH}" ]]; then
  echo "TARGET_BRANCH is required." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git not found." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: ${REPO_ROOT}" >&2
  exit 1
fi

if [[ "${ALLOW_DIRTY}" != "1" ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty. Commit/stash changes or set ALLOW_DIRTY=1." >&2
  exit 1
fi

git fetch --prune "${REMOTE_NAME}"

if ! git show-ref --verify --quiet "refs/remotes/${REMOTE_NAME}/${TARGET_BRANCH}"; then
  echo "Remote branch not found: ${REMOTE_NAME}/${TARGET_BRANCH}" >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
  git checkout "${TARGET_BRANCH}"
else
  git checkout -b "${TARGET_BRANCH}" "${REMOTE_NAME}/${TARGET_BRANCH}"
fi

git pull --ff-only "${REMOTE_NAME}" "${TARGET_BRANCH}"

SYSTEMCTL_CMD=("${SYSTEMCTL_BIN}")
if [[ "$(id -u)" -ne 0 ]]; then
  if [[ -n "${SUDO}" ]]; then
    SYSTEMCTL_CMD=(${SUDO} "${SYSTEMCTL_BIN}")
  else
    echo "Run as root or set SUDO=sudo to manage systemd." >&2
    exit 1
  fi
fi

if ! command -v "${SYSTEMCTL_BIN}" >/dev/null 2>&1; then
  echo "systemctl not found." >&2
  exit 1
fi

was_active=false
if "${SYSTEMCTL_CMD[@]}" is-active --quiet "${SERVICE_NAME}"; then
  was_active=true
  "${SYSTEMCTL_CMD[@]}" stop "${SERVICE_NAME}"
fi

if [[ "${was_active}" == "true" ]]; then
  "${SYSTEMCTL_CMD[@]}" start "${SERVICE_NAME}"
else
  echo "Service is not active; skipping restart."
fi
