#!/bin/sh

choice=$(
  printf '%s\n' \
    "󰍹  Display & Brightness" \
    "󰕾  Sound & Volume" \
    "󰤨  Network" \
    "󰤆  Power Options" \
    "󰈸  System Monitor" \
    "󰋗  System Info" \
  | rofi -dmenu -theme ~/.config/rofi/control-center-odyssey.rasi -p "Odyssey"
)

[ -z "$choice" ] && exit 0

case "$choice" in
  "󰍹  Display & Brightness")
    kitty -e sh ~/.config/scripts/cc-brightness.sh &
    ;;
  "󰕾  Sound & Volume")
    kitty -e alsamixer &
    ;;
  "󰤨  Network")
    kitty -e nmtui &
    ;;
  "󰤆  Power Options")
    kitty -e sh ~/.config/scripts/cc-power.sh &
    ;;
  "󰈸  System Monitor")
    kitty -e top &
    ;;
  "󰋗  System Info")
    kitty -e sh ~/.config/scripts/cc-sysinfo.sh &
    ;;
esac

exit 0
