#!/usr/bin/env bash

# Position terminal window
W=$(($(system_profiler SPDisplaysDataType | grep Resolution | awk '{print $2}' | head -1) / 2))
H=$(($(system_profiler SPDisplaysDataType | grep Resolution | awk '{print $4}' | head -1) / 2))

K=60
WW=$((W * K / 100))
WH=$((H * K / 100))
X=$(((W - WW) / 2))
Y=$(((H - WH) / 2))

osascript <<eof
tell application "Terminal"
    set bounds of front window to {$X, $Y, $((X + WW)), $((Y + WH))}
end tell
eof

cd -- "$(dirname -- "$BASH_SOURCE")"
cd ../../src

source .venv/bin/activate

# Settings come from the .env file shared with docker compose
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

python -m uvicorn main:app --host 127.0.0.1 --port 5005

echo
echo "Service running at: http://127.0.0.1:5005"
echo