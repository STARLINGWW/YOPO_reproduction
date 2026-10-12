#!/usr/bin/env bash
# Recreate the implement/workspace code view with symlinks (Ubuntu 22.04 / Linux).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
for name in src scripts configs docker ros2_ws tests external benchmarks vendor assets; do
  link="$here/$name"
  target="$root/$name"
  if [ -e "$link" ] || [ -L "$link" ]; then
    echo "exists: $name"
    continue
  fi
  if [ ! -d "$target" ]; then
    echo "missing target: $name"
    continue
  fi
  ln -s "$target" "$link"
  echo "linked: $name -> $target"
done
