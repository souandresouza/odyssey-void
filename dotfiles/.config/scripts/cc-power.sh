#!/bin/sh

choice=$(
  printf '%s\n' \
    "Logout" \
    "Shutdown" \
    "Reboot" \
    "Suspend" \
  | rofi -dmenu -theme ~/.config/rofi/odyssey.rasi -p "Power"
)

[ -z "$choice" ] && exit 0

case "$choice" in
  "Logout")
    labwc --exit
    ;;
  "Shutdown")
    sudo poweroff
    ;;
  "Reboot")
    sudo reboot
    ;;
  "Suspend")
    sudo zzz 2>/dev/null || loginctl suspend
    ;;
esac

exit 0
