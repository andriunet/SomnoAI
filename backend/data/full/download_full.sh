#!/bin/sh
# Descarga las 153 noches completas de Sleep-EDFx (PhysioNet, subconjunto sleep-cassette)
# a partir del índice ml/age_records.csv. ~8,7 GB en total. Se intenta primero el
# espejo S3 abierto (más rápido) y luego physionet.org, igual que download_demos.sh.
# Verifica cada archivo contra la columna sha (SHA1) de age_records.csv.
cd "$(dirname "$0")"
S3="https://physionet-open.s3.amazonaws.com/sleep-edfx/1.0.0/sleep-cassette"
PN="https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette"
INDEX="../../../ml/age_records.csv"

ok=0
skip=0
fail=0

tail -n +2 "$INDEX" | while IFS=, read -r subject night rtype age sex lights sha fname; do
  fname=$(echo "$fname" | tr -d '\r')
  sha=$(echo "$sha" | tr -d '\r')
  if [ -s "$fname" ]; then
    got=$(shasum "$fname" | cut -d' ' -f1)
    if [ "$got" = "$sha" ]; then
      echo "ok (ya existe): $fname"
      continue
    else
      echo "corrupto, re-descargando: $fname"
    fi
  fi
  echo "descargando $fname..."
  if curl -skf -o "$fname" "$S3/$fname" || curl -skf -o "$fname" "$PN/$fname?download"; then
    got=$(shasum "$fname" | cut -d' ' -f1)
    if [ "$got" != "$sha" ]; then
      echo "FALLÓ verificación sha1: $fname"
    fi
  else
    echo "FALLÓ descarga: $fname"
  fi
done
echo "Listo: $(ls SC4*.edf 2>/dev/null | wc -l | tr -d ' ') archivos EDF en $(pwd)"
