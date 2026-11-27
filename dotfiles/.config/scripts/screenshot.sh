#!/usr/bin/env bash
set -euo pipefail

# ========= CONFIG =========
BASE_DIR="$HOME/Imagens/Screenshots"

DATE=$(date +%d-%m-%Y)
TIMESTAMP=$(date +%d%m%Y_%H%M%S)

DIR="$BASE_DIR/$DATE"

# Modelos do tesseract baixados fora do pacote ficam aqui; se os pacotes
# tesseract-ocr-* estiverem instalados, o script prefere /usr/share/tessdata.
TESSDATA_USER="$HOME/.local/share/tesseract/tessdata"

# No Void Linux (XBPS) o executável se chama tesseract-ocr; em outras distros,
# tesseract. Resolve uma vez para usar o nome correto em toda a chamada;
# os caminhos absolutos cobrem um PATH limitado ao iniciar pelo WM.
TESSERACT_BIN=""
for tesseract_candidate in tesseract tesseract-ocr /usr/bin/tesseract /usr/bin/tesseract-ocr; do
  if command -v "$tesseract_candidate" >/dev/null 2>&1; then
    TESSERACT_BIN=$tesseract_candidate
    break
  fi
done

# ========= DETECT COMPOSITOR =========
detect_compositor() {
  if command -v mango >/dev/null 2>&1; then
    echo "mango"
  else
    echo "unknown"
  fi
}

COMPOSITOR=$(detect_compositor)

# ========= GET ACTIVE WINDOW GEOMETRY =========
# O MangoWM expõe um socket IPC que responde JSON:
#   get focusing-client -> {"x":..,"y":..,"width":..,"height":..,...}
# Não existe CLI pronto, então falamos com o socket via python3.
mango_socket() {
  local pid
  pid=$(pgrep -x mango 2>/dev/null | head -1) || return 1
  [[ -n "$pid" ]] || return 1
  local sock="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/mango-${pid}.sock"
  [[ -S "$sock" ]] || return 1
  printf '%s' "$sock"
}

get_window_geom() {
  case "$COMPOSITOR" in
    mango)
      local sock
      sock=$(mango_socket) || return 1

      local resp
      resp=$(printf 'get focusing-client\n' | timeout 2 python3 -c '
import socket, sys
sock = sys.argv[1]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(1.5)
s.connect(sock)
s.sendall(b"get focusing-client\n")
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        break
    buf += chunk
sys.stdout.write(buf.decode(errors="replace"))
' "$sock" 2>/dev/null) || return 1

      [[ -n "$resp" ]] || return 1
      # Erro do WM (ex.: nenhuma janela focada). Usa 'if' porque com
      # '&& return 1' o último comando do case viraria o status da função.
      if [[ "$resp" == *'"error"'* ]]; then
        return 1
      fi

      printf '%s' "$resp" | python3 -c '
import json, sys
d = json.load(sys.stdin)
w, h = int(d["width"]), int(d["height"])
if w <= 0 or h <= 0:
    sys.exit(1)
print("%d,%d %dx%d" % (int(d["x"]), int(d["y"]), w, h))
' 2>/dev/null
      ;;
    *)
      return 1
      ;;
  esac
}

# ========= HELP =========
usage() {
  echo "Uso: screenshot [all|monitor|region|window|annotate|ocr|qr]"
  exit 1
}

# ========= HELPERS =========
# Captura para arquivo e define MODE/FILE. A pasta do dia só é criada quando
# existe uma imagem para salvar (OCR/QR não criam pasta vazia).
capture() {
  local mode="$1"
  shift

  MODE="$mode"
  FILE="$DIR/screenshot_${MODE}_${TIMESTAMP}.png"
  mkdir -p "$DIR"
  grim "$@" "$FILE"
}

notify_error() {
  notify-send -u critical "$1" "${2:-}"
}

# Idiomas disponíveis em um diretório de dados do tesseract, na ordem de
# preferência deste script (português + inglês).
ocr_langs() {
  local dir="$1"
  local lang available_lang
  local -a available=() chosen=()

  mapfile -t available < <("$TESSERACT_BIN" --list-langs --tessdata-dir "$dir" 2>/dev/null | tail -n +2)
  for lang in por eng; do
    for available_lang in "${available[@]}"; do
      if [[ "$available_lang" == "$lang" ]]; then
        chosen+=("$lang")
        break
      fi
    done
  done

  ((${#chosen[@]})) || return 1
  (IFS=+; printf '%s' "${chosen[*]}")
}

# ========= MODES =========
case "${1:-}" in
  all)
    capture all
    ;;

  monitor)
    MONITOR=$(slurp -o -f "%o") || exit 0
    [[ -n "$MONITOR" ]] || exit 0
    capture "$MONITOR" -o "$MONITOR"
    ;;

  region)
    GEOM=$(slurp) || exit 0
    [[ -n "$GEOM" ]] || exit 0
    capture region -g "$GEOM"
    ;;

  window)
    GEOM=$(get_window_geom || true)

    if [[ -z "${GEOM:-}" ]]; then
      notify-send "Screenshot" "Erro ao obter janela ($COMPOSITOR)"
      exit 1
    fi

    capture window -g "$GEOM"
    ;;

  annotate)
    MODE="annotate"
    GEOM=$(slurp) || exit 0
    [[ -n "$GEOM" ]] || exit 0

    command -v satty >/dev/null || {
      notify_error "Anotação" "satty não encontrado (instale satty)"
      exit 1
    }

    mkdir -p "$DIR"
    FILE="$DIR/screenshot_annotate_${TIMESTAMP}.png"
    grim -g "$GEOM" - | satty -f - --output-filename "$FILE" --copy-command wl-copy || exit 0
    [[ -f "$FILE" ]] || exit 0

    notify-send -i "$FILE" "Screenshot Capturada" "$MODE • $(basename "$FILE")"
    echo "Salvo em: $FILE"
    exit 0
    ;;

  ocr)
    MODE="ocr"
    GEOM=$(slurp) || exit 0
    [[ -n "$GEOM" ]] || exit 0

    [[ -n "$TESSERACT_BIN" ]] || {
      notify_error "OCR" "tesseract não encontrado (instale tesseract ou tesseract-ocr)"
      exit 1
    }

    LANGS="${OCR_LANGS:-}"
    TESSDATA_ARGS=()
    if [[ -z "$LANGS" ]]; then
      if LANGS=$(ocr_langs /usr/share/tessdata); then
        :
      elif LANGS=$(ocr_langs "$TESSDATA_USER"); then
        TESSDATA_ARGS=(--tessdata-dir "$TESSDATA_USER")
      else
        notify_error "OCR" "Sem modelos do tesseract (instale tesseract-ocr-por e tesseract-ocr-eng)"
        exit 1
      fi
    fi

    RESULT=$(grim -g "$GEOM" - | "$TESSERACT_BIN" stdin stdout \
      --oem 1 --psm 6 -l "$LANGS" "${TESSDATA_ARGS[@]}" \
      -c preserve_interword_spaces=1 2>/dev/null) || true

    # Remove só espaços nas pontas; quebras de linha internas são preservadas.
    RESULT="${RESULT#"${RESULT%%[![:space:]]*}"}"
    RESULT="${RESULT%"${RESULT##*[![:space:]]}"}"

    [[ -n "$RESULT" ]] || {
      notify_error "OCR" "Nenhum texto encontrado na região"
      exit 1
    }

    printf '%s' "$RESULT" | wl-copy
    notify-send "OCR" "Texto copiado para a área de transferência"
    exit 0
    ;;

  qr)
    MODE="qr"
    GEOM=$(slurp) || exit 0
    [[ -n "$GEOM" ]] || exit 0

    command -v zbarimg >/dev/null || {
      notify_error "QR" "zbarimg não encontrado (instale zbar)"
      exit 1
    }

    RESULT=$(grim -g "$GEOM" - | zbarimg -q --raw -Sdisable -Sqrcode.enable - 2>/dev/null) || true

    [[ -n "$RESULT" ]] || {
      notify_error "QR" "Nenhum QR code encontrado na região"
      exit 1
    }

    # QR pode carregar segredo (otpauth://, tokens): não exibe o conteúdo e
    # marca a cópia como sensível.
    printf '%s' "$RESULT" | wl-copy --sensitive
    notify-send "QR" "Conteúdo copiado para a área de transferência"
    exit 0
    ;;

  *)
    usage
    ;;
esac

# ========= COPY =========
wl-copy < "$FILE"

# ========= FEEDBACK (SwayNC Thumbnail) =========
# O SwayNC processa nativamente o parâmetro -i como a prévia lateral se receber o caminho absoluto.
FILENAME=$(basename "$FILE")
notify-send -i "$FILE" "Screenshot Capturada" "$MODE • $FILENAME"
echo "Salvo em: $FILE"
