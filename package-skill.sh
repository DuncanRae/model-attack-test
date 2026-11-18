#!/usr/bin/env bash
# Builds the skill as one folder that stands on its own, and a zip of it:
#   dist/model-attack-test/            copy this into Claude's or Antigravity's skills folder
#   dist/model-attack-test-skill.zip   or upload this where a skill is added as a file
# The folder holds SKILL.md and a copy of the tool under scripts/. It is built from this source every time: never
# edit dist/ by hand. The tests are run first, and nothing is built if one fails.
set -euo pipefail
cd "$(dirname "$0")"
./run-tests.sh
version="$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' attack_test/__init__.py)"
grep -q "\"version\": \"$version\"" .claude-plugin/plugin.json || { echo "The version in .claude-plugin/plugin.json is not $version."; exit 1; }
grep -q "^## v$version " CHANGELOG.md || { echo "CHANGELOG.md has no entry for v$version."; exit 1; }
out="dist/model-attack-test"
rm -rf dist
mkdir -p "$out/scripts/attack_test" "$out/scripts/practice" "$out/scripts/packs/examples" "$out/scripts/targets/examples"
cp skills/model-attack-test/SKILL.md skills/model-attack-test/address-route.md "$out/"
cp attack-test "$out/scripts/"
cp attack_test/*.py "$out/scripts/attack_test/"
cp practice/*.py "$out/scripts/practice/"
cp packs/*.json "$out/scripts/packs/"
cp packs/examples/*.json "$out/scripts/packs/examples/"
cp targets/examples/*.json "$out/scripts/targets/examples/"
printf '%s\n' "$version" > "$out/VERSION"
chmod +x "$out/scripts/attack-test"
(cd dist && zip -q -r -X model-attack-test-skill.zip model-attack-test)
echo "Built v$version: $(pwd)/$out and $(pwd)/dist/model-attack-test-skill.zip"
