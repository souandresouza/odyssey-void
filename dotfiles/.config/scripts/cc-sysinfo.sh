#!/bin/sh
# PROMEMORIA: output utente in INGLESE, commenti in italiano.

clear
echo "=== System Info ==="
echo

echo "-- Kernel --"
uname -r
echo

echo "-- OS --"
if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "$NAME $VERSION"
else
  echo "Unknown OS"
fi
echo

echo "-- Uptime --"
uptime -p
echo

echo "-- CPU --"
lscpu | grep -E 'Model name|Architecture|CPU\(s\)' || echo "lscpu not available"
echo

echo "-- Memory --"
free -h
echo

echo "-- Disks (root + home) --"
df -h / /home 2>/dev/null || df -h
echo

echo
echo "Press Enter to exit..."
read _
