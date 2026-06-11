#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
check_empty() {
  local label="$1"
  shift
  local output
  output="$("$@" || true)"
  if [[ -n "$output" ]]; then
    printf 'FAIL: %s\n%s\n' "$label" "$output"
    fail=1
  else
    printf 'OK: %s\n' "$label"
  fi
}

check_empty "tracked files over 10 MiB" sh -c \
  'git ls-files -z | xargs -0 -I{} sh -c '\''test ! -f "$1" || test "$(wc -c < "$1")" -le 10485760 || echo "$1"'\'' _ {}'
check_empty "forbidden tracked paths" sh -c \
  'git ls-files | grep -E "(^|/)(datasets|node_modules|dist|app/data|app/models|edgeface|Silent-Face-Anti-Spoofing|CR-FIQA|insightface|faiss)/" | grep -vE "app/(data|models)/\\.gitkeep$"'
check_empty "forbidden binary/model extensions" sh -c \
  'git ls-files | grep -Ei "\\.(pt|pth|onnx|caffemodel|faiss|db|sqlite|npy|npz|bin)$"'
check_empty "absolute personal paths" sh -c \
  'git grep -nE "/Users/[^/]+|C:\\\\Users\\\\[^\\\\]+" -- . ":(exclude)scripts/public_release_audit.sh"'
check_empty "likely committed secrets" sh -c \
  'git grep -nE "AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----" -- . ":(exclude)scripts/public_release_audit.sh"'
private_re='高''申宸|杨''昊澎|高''利岩|代''思杰|韩''清泉|焦''思洋|yuli_''xia|222022326062003'
check_empty "project-member private identifiers" sh -c \
  "git grep -nE '$private_re' -- . ':(exclude)scripts/public_release_audit.sh' || true"

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "Public release audit passed."
