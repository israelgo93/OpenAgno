#!/usr/bin/env bash
set -euo pipefail

claude mcp add-json --scope project openagno-docs '{"type":"http","url":"https://docs.openagno.com/mcp"}'
