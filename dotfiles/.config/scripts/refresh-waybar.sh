#!/usr/bin/env bash
set -u

WAYBAR="$HOME/.local/bin/waybar-mango"
CONFIG="$HOME/.config/waybar/config.jsonc"
STYLE="$HOME/.config/waybar/style.css"

if pgrep -x waybar-mango >/dev/null 2>&1; then
    pkill -SIGUSR2 -x waybar-mango 2>/dev/null || true
    echo "Waybar recarregada"
else
    pkill -x waybar 2>/dev/null || true
    setsid -f "$WAYBAR" -c "$CONFIG" -s "$STYLE" </dev/null >/dev/null 2>&1 &
    echo "Waybar iniciada"
fi
