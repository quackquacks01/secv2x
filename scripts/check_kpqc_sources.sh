#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${1:-$HOME/kpqc-work}"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

clone_or_update() {
  local url="$1"
  local dir="$2"
  if [ -d "$dir/.git" ]; then
    git -C "$dir" pull --ff-only
  else
    git clone "$url" "$dir"
  fi
}

clone_or_update https://github.com/samsungsds-research-papers/AIMer.git AIMer
clone_or_update https://github.com/CryptoLabInc/HAETAE.git HAETAE

echo "=== AIMer revision ==="
git -C AIMer rev-parse HEAD
git -C AIMer log -1 --oneline

echo "=== AIMer build files ==="
find AIMer -type f \( -name Makefile -o -name CMakeLists.txt -o -name 'README*' \) | sort

echo "=== AIMer API and size macros ==="
grep -R "crypto_sign_keypair\|crypto_sign_signature\|crypto_sign_verify" -n AIMer/Reference_Implementation | head -50 || true
grep -R "CRYPTO_PUBLICKEYBYTES\|CRYPTO_SECRETKEYBYTES\|CRYPTO_BYTES" -n AIMer/Reference_Implementation | head -50 || true

echo "=== HAETAE revision ==="
git -C HAETAE rev-parse HEAD
git -C HAETAE log -1 --oneline

if [ -f HAETAE/HAETAE.zip ]; then
  rm -rf HAETAE/unpacked
  mkdir -p HAETAE/unpacked
  unzip -q HAETAE/HAETAE.zip -d HAETAE/unpacked
fi

echo "=== HAETAE build files ==="
find HAETAE -type f \( -name Makefile -o -name CMakeLists.txt -o -name 'README*' \) | sort

echo "=== HAETAE API and size macros ==="
grep -R "crypto_sign_keypair\|crypto_sign_signature\|crypto_sign_verify" -n HAETAE/unpacked | head -50 || true
grep -R "CRYPTO_PUBLICKEYBYTES\|CRYPTO_SECRETKEYBYTES\|CRYPTO_BYTES" -n HAETAE/unpacked | head -50 || true
