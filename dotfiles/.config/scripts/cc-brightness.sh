#!/bin/sh
# PROMEMORIA: output utente in INGLESE, commenti in italiano.

clear
echo "=== Display & Brightness ==="
echo

if ! command -v brightnessctl >/dev/null 2>&1; then
  echo "brightnessctl is not installed."
  echo
  echo "Install it with:"
  echo "  sudo xbps-install -S brightnessctl"
  echo
  echo "Press Enter to exit..."
  read _
  exit 0
fi

echo "-- Current brightness --"
brightnessctl info
echo

echo "Choose a level:"
echo "  1) 20%"
echo "  2) 40%"
echo "  3) 60%"
echo "  4) 80%"
echo "  5) 100%"
echo "  6) -10% (darker)"
echo "  7) +10% (brighter)"
echo "  8) Exit"
echo
printf "Choice [1-8]: "
read ans

case "$ans" in
  1) brightnessctl set 20% ;;
  2) brightnessctl set 40% ;;
  3) brightnessctl set 60% ;;
  4) brightnessctl set 80% ;;
  5) brightnessctl set 100% ;;
  6) brightnessctl set 10%- ;;
  7) brightnessctl set 10%+ ;;
  *) ;;
esac

echo
echo "New brightness:"
brightnessctl info
echo
echo "Press Enter to exit..."
read _
