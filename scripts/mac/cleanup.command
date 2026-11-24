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

rm -rf ../../.claude
rm -rf ../../src/.venv
rm -rf ../../src/__pycache__
rm -rf ../../src/.pytest_cache
rm -rf ../../src/api/__pycache__
rm -rf ../../src/core/__pycache__
rm -rf ../../src/core/agents/__pycache__
rm -rf ../../src/core/tools/__pycache__
rm -rf ../../src/database/__pycache__
rm -rf ../../src/tests/unit_tests/__pycache__
rm -rf ../../src/tests/integration_tests/__pycache__

rm -f ../../src/database/*.xhtml
rm -f ../../src/tests/integration_tests/test_act.md

echo
read -p "Press any key to continue..."