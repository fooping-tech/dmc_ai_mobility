#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

SERVICE_NAME="${SERVICE_NAME:-dmc-ai-mobility.service}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"
LOCK_FILE="${LOCK_FILE:-/tmp/dmc_ai_mobility_pull.lock}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"
SUDO="${SUDO:-}"

if ! command -v git >/dev/null 2>&1; then
  echo "git not found." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: ${REPO_ROOT}" >&2
  exit 1
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "Another update is already running; exiting."
    exit 0
  fi
fi

if [[ "${ALLOW_DIRTY}" != "1" ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty. Commit/stash changes or set ALLOW_DIRTY=1." >&2
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${BRANCH}" == "HEAD" ]]; then
  echo "Detached HEAD; refusing to pull." >&2
  exit 1
fi

git fetch --prune "${REMOTE_NAME}"

if ! git show-ref --verify --quiet "refs/remotes/${REMOTE_NAME}/${BRANCH}"; then
  echo "Remote branch not found: ${REMOTE_NAME}/${BRANCH}" >&2
  exit 1
fi

LOCAL_REV="$(git rev-parse HEAD)"
REMOTE_REV="$(git rev-parse "${REMOTE_NAME}/${BRANCH}")"

if [[ "${LOCAL_REV}" == "${REMOTE_REV}" ]]; then
  echo "Already up to date."
  exit 0
fi

if git merge-base --is-ancestor "${REMOTE_REV}" "${LOCAL_REV}"; then
  echo "Local branch is ahead of remote; skipping pull."
  exit 0
fi

if ! git merge-base --is-ancestor "${LOCAL_REV}" "${REMOTE_REV}"; then
  echo "Non-fast-forward update detected; aborting." >&2
  exit 1
fi

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
stopped=false
pull_applied=false

cleanup() {
  if [[ "${stopped}" == "true" && "${pull_applied}" != "true" ]]; then
    "${SYSTEMCTL_CMD[@]}" start "${SERVICE_NAME}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if "${SYSTEMCTL_CMD[@]}" is-active --quiet "${SERVICE_NAME}"; then
  was_active=true
  "${SYSTEMCTL_CMD[@]}" stop "${SERVICE_NAME}"
  stopped=true
fi

git pull --ff-only "${REMOTE_NAME}" "${BRANCH}"
pull_applied=true

if [[ "${was_active}" == "true" ]]; then
  "${SYSTEMCTL_CMD[@]}" start "${SERVICE_NAME}"
  stopped=false
else
  echo "Service is not active; skipping restart."
fi
