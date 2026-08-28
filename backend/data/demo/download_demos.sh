#!/bin/sh
# Descarga las 3 noches demo de Sleep-EDFx (PhysioNet) usadas por la API.
# ~148 MB en total. Se intenta primero el espejo S3 (más rápido) y luego physionet.org.
cd "$(dirname "$0")"
S3="https://physionet-open.s3.amazonaws.com/sleep-edfx/1.0.0/sleep-cassette"
PN="https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette"
for f in SC4001E0-PSG.edf SC4001EC-Hypnogram.edf \
         SC4701E0-PSG.edf SC4701EC-Hypnogram.edf \
         SC4021E0-PSG.edf SC4021EH-Hypnogram.edf; do
  if [ -s "$f" ]; then echo "ya existe: $f"; continue; fi
  echo "descargando $f…"
  curl -skf -o "$f" "$S3/$f" || curl -skf -o "$f" "$PN/$f?download" || { echo "FALLÓ $f"; exit 1; }
done
echo "Listo: $(ls SC4*-PSG.edf | wc -l | tr -d ' ') PSG + hipnogramas en $(pwd)"
