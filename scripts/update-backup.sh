#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
home="${HOME:-}"
manifest="$root/manifest.txt"
dest_root="$root/dotfiles"

if [[ -z "$home" ]]; then
  printf 'HOME não definido\n' >&2
  exit 1
fi

while IFS= read -r rel || [[ -n "$rel" ]]; do
  [[ -z "$rel" ]] && continue
  src="$home/$rel"
  dest="$dest_root/$rel"
  if [[ ! -e "$src" ]]; then
    printf 'ausente: %s\n' "$rel" >&2
    continue
  fi
  mkdir -p "$(dirname -- "$dest")"
  cp -a -- "$src" "$dest"
  printf 'copiado: %s\n' "$rel"
done < "$manifest"

escaped_home="$(printf '%s' "$home" | sed 's|[.[\*^$&|\\]|\\&|g')"
while IFS= read -r -d '' file; do
  if grep -Fq "$home" "$file" 2>/dev/null; then
    tmp="$(mktemp)"
    sed "s|$escaped_home|__HOME__|g" "$file" > "$tmp"
    cat "$tmp" > "$file"
    rm -f -- "$tmp"
    printf 'sanitizado: %s\n' "${file#"$dest_root/"}"
  fi
done < <(find "$dest_root" -type f -print0)

if command -v xbps-query >/dev/null 2>&1; then
  xbps-query -m | sed -E 's/-[^-]*_[0-9]+$//' | sort > "$root/packages/manual.txt"
  printf 'pacotes atualizados: packages/manual.txt\n'
else
  printf 'xbps-query não encontrado; packages/manual.txt preservado\n' >&2
fi

printf '\nBackup atualizado. Rode scripts/check-secrets.sh antes de commitar.\n'
