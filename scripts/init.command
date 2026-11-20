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

ensure_docker() {
    docker info >/dev/null 2>&1 && return 0
    echo "Starting Docker Desktop..."
    open -a Docker || return 1
    for _ in $(seq 1 60); do
        sleep 2
        docker info >/dev/null 2>&1 && return 0
    done
    return 1
}

cd -- "$(dirname -- "$BASH_SOURCE")"

cd ../src
python3 -m venv .venv
source .venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt

if ensure_docker; then
    docker compose down -v --remove-orphans
    docker compose up -d weaviate
else
    echo "Error: Docker could not be started."
fi

echo
read -p "Press any key to continue..."