#!/bin/sh
# ~/.config/scripts/colors/fuzzel-colors.sh
# Gera configuração de cores do fuzzel baseado no wallpaper atual (via Pywal)

COLORS_FILE="$HOME/.cache/wal/colors.css"
FUZZEL_FILE="$HOME/.config/fuzzel/colors-fuzzel.ini"

WALLPAPER=""
pid=$(pgrep -x swaybg 2>/dev/null | head -n 1 || true)
if [ -n "$pid" ] && [ -r "/proc/$pid/cmdline" ]; then
    WALLPAPER=$(tr '\0' '\n' < "/proc/$pid/cmdline" | awk 'p {print; exit} /^-i$|^--image$/ {p=1}')
fi
[ -f "$WALLPAPER" ] || WALLPAPER="$HOME/.cache/current_wallpaper.png"

if [ -f "$WALLPAPER" ]; then
    cached_wallpaper=""
    if [ -f "$COLORS_FILE" ]; then
        cached_wallpaper=$(grep -- '--wallpaper:' "$COLORS_FILE" | head -n 1 | sed -n 's/.*url("\?\([^")]*\)"\?).*/\1/p')
    fi
    if [ ! -f "$COLORS_FILE" ] || [ "$cached_wallpaper" != "$WALLPAPER" ] || [ "$WALLPAPER" -nt "$COLORS_FILE" ]; then
        PALETTE_TOOL="${PALETTE_TOOL:-ruwall}"
        if command -v "$PALETTE_TOOL" >/dev/null 2>&1; then
            PALETTE=$(command -v "$PALETTE_TOOL")
        elif [ -x "$HOME/.local/bin/$PALETTE_TOOL" ]; then
            PALETTE="$HOME/.local/bin/$PALETTE_TOOL"
        else
            PALETTE=$(command -v wal 2>/dev/null || true)
        fi
        if [ -n "$PALETTE" ]; then
            "$PALETTE" -n -e -i "$WALLPAPER" >/dev/null 2>&1 ||
                echo "aviso: não foi possível gerar a paleta a partir de $WALLPAPER" >&2
        fi
    fi
fi

if [ ! -f "$COLORS_FILE" ]; then
    echo "ERRO: sem paleta em $COLORS_FILE"
    echo "Gere uma com:"
    echo "  ~/.config/scripts/run-scripts.sh            # usa o wallpaper atual"
    echo "  ~/.config/scripts/run-scripts.sh <imagem>   # de um arquivo"
    echo "  (PALETTE_TOOL=wal volta ao pywal)"
    echo "Sem paleta em ~/.cache/wal. Gere uma com:"
    echo "  ~/.config/scripts/run-scripts.sh            # usa o wallpaper atual"
    echo "  ~/.config/scripts/run-scripts.sh <imagem>   # de um arquivo"
    echo "  (ou PALETTE_TOOL=wal para voltar ao pywal)"
    exit 1
fi

# Extrair cores do formato Pywal/CSS (--color0: #xxx;)
extract_color() {
    grep -- "--color$1:" "$COLORS_FILE" | head -1 | awk -F': ' '{print $2}' | tr -d '; '
}

# Extrair também background, foreground e cursor
background=$(grep -- "--background:" "$COLORS_FILE" | head -1 | awk -F': ' '{print $2}' | tr -d '; ')
foreground=$(grep -- "--foreground:" "$COLORS_FILE" | head -1 | awk -F': ' '{print $2}' | tr -d '; ')
cursor=$(grep -- "--cursor:" "$COLORS_FILE" | head -1 | awk -F': ' '{print $2}' | tr -d '; ')

# Extrair cores 0-15
color0=$(extract_color 0)
color1=$(extract_color 1)
color2=$(extract_color 2)
color3=$(extract_color 3)
color4=$(extract_color 4)
color5=$(extract_color 5)
color6=$(extract_color 6)
color7=$(extract_color 7)
color8=$(extract_color 8)
color9=$(extract_color 9)
color10=$(extract_color 10)
color11=$(extract_color 11)
color12=$(extract_color 12)
color13=$(extract_color 13)
color14=$(extract_color 14)
color15=$(extract_color 15)

# Limpar cores (remover colchetes, espaços e #)
clean_color() {
    echo "$1" | tr -d '[]# '
}

# Verificar se as cores foram extraídas
if [ -z "$color0" ] || [ -z "$background" ] || [ -z "$foreground" ]; then
    echo "ERRO: a paleta em $COLORS_FILE não tem cores utilizáveis."
    echo "Regere com: ~/.config/scripts/run-scripts.sh"
    exit 1
fi

mkdir -p "$(dirname "$FUZZEL_FILE")"

# Criar configuração com alpha ff
# Mapeamento otimizado para melhor contraste e legibilidade
cat > "$FUZZEL_FILE" << EOF
[colors]
background=${background}ff
prompt=${foreground}ff
text=${foreground}ff
placeholder=${color8}ff
input=${foreground}ff
match=${color14}ff
selection=${color4}ff
selection-text=${background}ff
selection-match=${color14}ff
border=${color4}ff
EOF

# Recarrega o fuzzel se estiver em execução
pkill -SIGUSR1 -x fuzzel 2>/dev/null || true

echo "✅ Cores do fuzzel atualizadas com base no wallpaper atual"
