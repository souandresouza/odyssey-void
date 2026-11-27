#!/usr/bin/env bash
# ~/.config/scripts/colors/fastfetch-colors.sh
# Regenera a configuração do fastfetch de forma neutra (logo da distro e
# informações do sistema). A paleta do terminal vem do wal/ruwall, então o
# fastfetch acompanha o tema automaticamente.

set -eu

CONFIG_DIR="$HOME/.config/fastfetch"
CONFIG_FILE="$CONFIG_DIR/config.jsonc"

mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_FILE" << 'EOF'
{
    "$schema": "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json",
    "logo": {
        "source": "~/.config/fastfetch/odyssey.txt",
        "type": "file",
        "width": 20,
        "height": 13,
        "color": { "1": "red" },
        "padding": { "right": 2 }
    },
    "modules": [
        "title", "separator", "os", "host", "kernel",
        "uptime", "packages", "shell", "de", "wm",
        "cpu", "memory", "colors"
    ]
}
EOF

echo "fastfetch: configuração do Odyssey atualizada em $CONFIG_FILE"
