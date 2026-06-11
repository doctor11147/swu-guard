#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

clone_pinned() {
  local url="$1" dir="$2" revision="$3"
  if [[ ! -d "$ROOT/$dir/.git" ]]; then
    git clone "$url" "$ROOT/$dir"
  fi
  git -C "$ROOT/$dir" fetch --tags --prune
  git -C "$ROOT/$dir" checkout --detach "$revision"
}

clone_pinned https://github.com/otroshi/edgeface.git edgeface ce86851cfc37979a9cd2558598d0e9bc592cbba3
clone_pinned https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git Silent-Face-Anti-Spoofing b6d5f04ad78778917853b25c778acef6d5626d15

echo "Third-party source trees are ready and ignored by Git."
echo "Review THIRD_PARTY_NOTICES.md and MODEL_MANIFEST.md before use."
