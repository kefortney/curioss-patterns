#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Starting CURIOSS Pattern Explorer at http://localhost:8765"
python3 -m uvicorn app:app --port 8765 --reload
