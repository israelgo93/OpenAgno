#!/usr/bin/env bash
# OpenAgno bootstrap helper for local development.

set -euo pipefail

echo
echo "========================================"
echo "  OpenAgno bootstrap"
echo "========================================"
echo

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=${version%%.*}
        minor=${version##*.}
        if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10 or newer is required."
    exit 1
fi

echo "Python detected: $($PYTHON --version)"

if [ ! -d ".venv" ]; then
    echo
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo
echo "Upgrading pip..."
python -m pip install --upgrade pip >/dev/null

echo "Installing OpenAgno with developer and protocol extras..."
python -m pip install -e '.[dev,protocols]' >/dev/null

if [ ! -d "workspace" ]; then
    echo
    echo "Initializing default workspace..."
    openagno init --template personal_assistant
else
    echo
    echo "Workspace already exists. Skipping template initialization."
fi

echo
echo "Validating workspace..."
openagno validate

echo
echo "========================================"
echo "  Bootstrap complete"
echo "========================================"
echo
echo "Next commands:"
echo "  openagno start --foreground"
echo "  openagno start"
echo "  openagno status"
echo "  openagno logs --follow"
echo
echo "Open the runtime at: http://localhost:8000"
echo
