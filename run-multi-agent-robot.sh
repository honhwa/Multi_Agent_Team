#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

export OFFICETOOL_APP_PROFILE="${OFFICETOOL_APP_PROFILE:-multi_agent_robot}"
export OFFICETOOL_APP_MODULE="${OFFICETOOL_APP_MODULE:-app.multi_agent_robot_main:app}"
export OFFICETOOL_APP_PORT="${OFFICETOOL_APP_PORT:-8080}"

exec ./run.sh
