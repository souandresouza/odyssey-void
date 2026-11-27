#!/bin/sh
set -e

list="$HOME/.config/mango/emoji-list.txt"
[ -f "$list" ] || exit 1

selected=$(fuzzel --dmenu --prompt " Emoji: " --match-mode=exact --no-sort --no-icons -l 20 < "$list") || exit 0
[ -n "$selected" ] || exit 0

printf '%s' "${selected%%[ 	]*}" | wl-copy
