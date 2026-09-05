#!/bin/bash
# Completa a cópia dos 7 arquivos que ficaram "dataless" (cloud-only) no OneDrive.
# Requisito: app OneDrive aberto e sincronizado (logado). Depois de rodar, apague este script.
set -u
SRC="$HOME/Library/CloudStorage/OneDrive-Pessoal/Projects/python/asrl"
DST="$HOME/Documents/asrl"
FILES=(AGENTS.md CLAUDE.md docs/tutorial.md docs/tecnica/pipeline.md docs/tecnica/busca-dsl.md docs/tecnica/saidas-funil.md docs/como-fazer/aquisicao-pdfs.md)
ok=0; fail=0
for f in "${FILES[@]}"; do
  [ -s "$DST/$f" ] && { echo "já existe: $f"; ok=$((ok+1)); continue; }
  mkdir -p "$DST/$(dirname "$f")"
  for tent in 1 2 3 4 5; do
    if cat "$SRC/$f" > "$DST/$f" 2>/dev/null && [ -s "$DST/$f" ]; then
      echo "copiado: $f ($(wc -c < "$DST/$f") bytes)"; ok=$((ok+1)); break
    fi
    sleep 5
    [ "$tent" = "5" ] && { fail=$((fail+1)); echo "FALHOU: $f (ainda cloud-only?)"; }
  done
done
echo "----"
echo "concluídos: $ok/7 | pendentes: $fail"
[ $fail -eq 0 ] && rm -f "$0" && echo "script removido (missão cumprida)."
