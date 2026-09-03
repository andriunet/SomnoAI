#!/bin/sh
# Siembra el histórico compartido con noches reales de Sleep-EDFx.
#
# Por cada noche de scripts/seed_list.txt: descarga el PSG y su hipnograma del
# espejo de PhysioNet, los empaqueta en un .zip (así el pipeline usa el
# hipnograma ANOTADO y no necesita estimarlo con YASA), lo manda a la API y
# borra los EDF. La edad la detecta la API del encabezado del EDF.
#
# Al final imprime el MAE realizado — la media de |BAI| sobre lo sembrado.
#
#   sh scripts/seed_records.sh            # contra la API local
#   API=http://otra:8000/api/v1 sh ...    # contra otra
set -eu

cd "$(dirname "$0")/.."
API="${API:-http://localhost:8000/api/v1}"
LIST="scripts/seed_list.txt"
S3="https://physionet-open.s3.amazonaws.com/sleep-edfx/1.0.0/sleep-cassette"
PN="https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette"

WORK="$(mktemp -d)"
RESULTS="$WORK/results.txt"
: > "$RESULTS"
trap 'rm -rf "$WORK"' EXIT INT TERM

echo "API: $API"
TOKEN=$(curl -sS -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"superusuario","password":"somnoai2026"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
[ -n "$TOKEN" ] || { echo "ERROR: no se pudo autenticar contra $API"; exit 1; }
echo "autenticado."

TOTAL=$(grep -c . "$LIST")
N=0
while read -r PSG HYP AGE; do
  [ -n "$PSG" ] || continue
  N=$((N + 1))
  printf '\n[%d/%d] %s (índice: %s años)\n' "$N" "$TOTAL" "$PSG" "$AGE"

  for F in "$PSG" "$HYP"; do
    curl -sSf -o "$WORK/$F" "$S3/$F" 2>/dev/null \
      || curl -sSf -o "$WORK/$F" "$PN/$F?download" \
      || { echo "  FALLÓ la descarga de $F — se salta esta noche"; continue 2; }
  done

  ZIP="$WORK/${PSG%-PSG.edf}.zip"
  python3 - "$ZIP" "$WORK/$PSG" "$WORK/$HYP" <<'PY'
import sys, zipfile
zip_path, *files = sys.argv[1:]
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f, arcname=f.rsplit("/", 1)[-1])
PY

  echo "  analizando (puede tardar minutos)…"
  RESP="$WORK/resp.json"
  if ! curl -sS -X POST "$API/records/analyze" \
        -H "Authorization: Bearer $TOKEN" -F "file=@$ZIP" -o "$RESP"; then
    echo "  FALLÓ la petición a la API"
    rm -f "$WORK/$PSG" "$WORK/$HYP" "$ZIP"
    continue
  fi

  python3 - "$RESP" "$RESULTS" <<'PY'
import json, sys
resp, results = sys.argv[1], sys.argv[2]
d = json.load(open(resp))
if "error" in d:
    print(f"  ERROR de la API: {d['error'].get('message', d['error'])}")
    sys.exit(0)
print(f"  → {d['subject_code']}: edad {d['chronological_age']}, "
      f"cerebral {d['brain_age']}, BAI {d['bai']:+.1f} "
      f"({'sobre el umbral' if d['over_threshold'] else 'en rango'})")
with open(results, "a") as fh:
    fh.write(f"{d['chronological_age']} {d['brain_age']} {d['bai']}\n")
PY

  rm -f "$WORK/$PSG" "$WORK/$HYP" "$ZIP"
done < "$LIST"

echo
echo "════════════════════════════════════════════"
python3 - "$RESULTS" <<'PY'
import sys
rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
if not rows:
    print("No se sembró ningún registro.")
    sys.exit(1)
bais = [abs(float(r[2])) for r in rows]
mae = sum(bais) / len(bais)
print(f"Registros sembrados : {len(rows)}")
print(f"MAE realizado       : {mae:.2f} años   (objetivo ≈ 9)")
print(f"|BAI| mín / máx     : {min(bais):.1f} / {max(bais):.1f}")
over = sum(1 for b in bais if b > 10)
print(f"Sobre el umbral ±10 : {over} de {len(rows)}")
PY
echo "════════════════════════════════════════════"
