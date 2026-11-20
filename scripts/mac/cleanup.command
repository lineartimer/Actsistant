#!/usr/bin/env bash
echo
echo "Cleaning up..."
echo

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

if ensure_docker; then
    (cd ../../src && docker compose down -v --remove-orphans)
else
    echo "Docker could not be started. Cleanup of containers failed."
fi

rm -rf ../../src/.venv
rm -rf ../../src/__pycache__
rm -rf ../../src/api/__pycache__
rm -rf ../../src/database/__pycache__
rm -f ../../src/database/*.xhtml

echo
read -p "Press any key to continue..."