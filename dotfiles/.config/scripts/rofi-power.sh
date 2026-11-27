#!/bin/sh
# Odyssey power menu — rofi
CHOICE=$(printf "Logout\nReboot\nSuspend\nShutdown" | \
    rofi -dmenu -p "power" -theme ~/.config/rofi/power-odyssey.rasi)

case "$CHOICE" in
    Logout)   labwc --exit ;;
    Reboot)   loginctl reboot ;;
    Suspend)  loginctl suspend ;;
    Shutdown) loginctl poweroff ;;
esac
