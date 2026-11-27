#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
scan_root="$root/dotfiles"
regex='gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|(password|passwd|api[_-]?key|secret|token)[[:space:]]*=[[:space:]]*[^#[:space:]]|/home/[a-z][a-z0-9._-]{2,}/'

found=0
while IFS= read -r -d '' file; do
  while IFS= read -r line; do
    printf '%s:%s\n' "${file#"$root/"}" "$line"
    found=1
  done < <(grep -nE "$regex" "$file" 2>/dev/null || true)
done < <(find "$scan_root" -type f -print0)

if (( found )); then
  printf '\nPossíveis dados sensíveis encontrados. Revise antes de publicar.\n' >&2
  exit 1
fi

printf 'OK: nenhum segredo ou caminho pessoal encontrado em dotfiles/.\n'
