#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-8000}"

echo "啟動本機網頁預覽..."
echo "URL: http://${HOST}:${PORT}"
python3 web_preview.py --host "$HOST" --port "$PORT"
