#!/bin/sh
# Odyssey power menu — rofi
CHOICE=$(printf "Logout\nReboot\nSuspend\nShutdown" | \
    rofi -dmenu -p "power" -theme ~/.config/rofi/power-odyssey.rasi)

case "$CHOICE" in
    Logout)   mmsg dispatch quit || loginctl terminate-session "${XDG_SESSION_ID:-}" ;;
    Reboot)   loginctl reboot ;;
    Suspend)  loginctl suspend ;;
    Shutdown) loginctl poweroff ;;
esac
