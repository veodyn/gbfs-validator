#!/usr/bin/env bash
# Rebuild the pinned upstream clone. Idempotent: safe to rerun.
set -euo pipefail
cd "$(dirname "$0")/.."

PIN=b734086ccdf93b5acd72bb349c6fda0c9f64fd39

if [ ! -d upstream/.git ]; then
  git clone https://github.com/MobilityData/gbfs-validator upstream
fi
git -C upstream fetch --quiet origin "$PIN"
git -C upstream checkout --quiet "$PIN"
git -C upstream submodule update --init --quiet

# Frozen lockfile: goldens are only reproducible if ajv resolves to the same
# version every time. Deps hoist to upstream/node_modules (yarn workspace).
yarn --cwd upstream install --frozen-lockfile --silent
