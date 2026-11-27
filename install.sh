#!/usr/bin/env bash
set -euo pipefail

src_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/dotfiles"
target="${HOME:-}"
dry_run=0
skip_existing=0
no_backup=0

usage() {
  printf '%s\n' \
    "Uso: ./install.sh [opções]" \
    "" \
    "  --dry-run         mostra o que seria instalado" \
    "  --skip-existing   mantém arquivos que já existem" \
    "  --no-backup       não guarda a versão anterior" \
    "  --target CAMINHO  instala em outro HOME" \
    "  -h, --help        mostra esta ajuda"
}

while (($#)); do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --skip-existing) skip_existing=1 ;;
    --no-backup) no_backup=1 ;;
    --target)
      shift
      target="${1:-}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Opção desconhecida: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -z "$target" || "$target" == "/" ]]; then
  printf 'Destino inválido: %s\n' "$target" >&2
  exit 2
fi
if [[ ! -d "$src_root" ]]; then
  printf 'Pasta dotfiles não encontrada: %s\n' "$src_root" >&2
  exit 1
fi
if (( ! dry_run )); then
  mkdir -p "$target"
fi
target="$(cd -- "$target" && pwd -P)"

stamp="$(date +%Y%m%d-%H%M%S)"
backup_root="$target/.odyssey-void-backup/$stamp"
installed=0
skipped=0
backed_up=0

while IFS= read -r -d '' src; do
  rel="${src#"$src_root/"}"
  dest="$target/$rel"
  action="install"

  if [[ -e "$dest" || -L "$dest" ]]; then
    if cmp -s "$src" "$dest"; then
      skipped=$((skipped + 1))
      continue
    fi
    if (( skip_existing )); then
      action="skip"
    elif (( ! dry_run )) && (( ! no_backup )); then
      mkdir -p "$backup_root/$(dirname -- "$rel")"
      cp -a -- "$dest" "$backup_root/$rel"
      backed_up=$((backed_up + 1))
    fi
  fi

  if (( dry_run )); then
    printf 'dry-run: %s %s\n' "$action" "$rel"
    continue
  fi

  if [[ "$action" == "skip" ]]; then
    skipped=$((skipped + 1))
    printf 'skip     %s\n' "$rel"
    continue
  fi

  mkdir -p "$(dirname -- "$dest")"
  if [[ -L "$dest" ]]; then
    rm -f -- "$dest"
  fi
  cp -p -- "$src" "$dest"

  if grep -Fq '__HOME__' "$dest" 2>/dev/null; then
    tmp="$(mktemp)"
    sed "s|__HOME__|$target|g" "$dest" > "$tmp"
    cat "$tmp" > "$dest"
    rm -f -- "$tmp"
  fi

  installed=$((installed + 1))
  printf 'install  %s\n' "$rel"
done < <(find "$src_root" -type f -print0 | sort -z)

printf '\nInstalados: %d | Ignorados: %d | Backup: %d\n' "$installed" "$skipped" "$backed_up"
if (( backed_up > 0 )); then
  printf 'Backups em: %s\n' "$backup_root"
fi
