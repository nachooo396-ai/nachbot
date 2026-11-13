#!/usr/bin/env bash
# Guarda salida.txt en la rama "estado" (ESTADO.md = última pasada, REGISTRO.md = historial).
set -u
WT=estado-wt
FECHA=$(TZ=Europe/Madrid date '+%Y-%m-%d %H:%M')
cd "$WT" || exit 0
git pull -q --rebase origin estado 2>/dev/null || true
{ echo "# Estado de NachBot"; echo; echo "Última pasada: $FECHA (hora de España)"; echo;
  sed 's/^/- /' ../salida.txt; } > ESTADO.md
{ echo "## $FECHA"; sed 's/^/- /' ../salida.txt; echo; [ -f REGISTRO.md ] && head -n 3000 REGISTRO.md; } > r.tmp
mv r.tmp REGISTRO.md
git add ESTADO.md REGISTRO.md
git commit -qm "Estado $FECHA" && git push -q origin estado
