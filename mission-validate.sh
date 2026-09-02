#!/bin/sh
set -eu

project_root=$(pwd -P)
git_common_dir=$(git rev-parse --path-format=absolute --git-common-dir)
primary_root=$(dirname "$git_common_dir")
project_python="$primary_root/.venv/bin/python"

if [ ! -x "$project_python" ]; then
  project_python=$(command -v python3)
fi

for test_file in tests/test_*.py; do
  if [ "$test_file" = "tests/test_mcp_server.py" ] \
    && ! "$project_python" -c 'import mcp' >/dev/null 2>&1; then
    echo "SKIP $test_file (optional mcp dependency is not installed)"
    continue
  fi
  PYTHONPATH="$project_root/src" "$project_python" -m unittest "$test_file"
done
node --test tests/*.test.js
