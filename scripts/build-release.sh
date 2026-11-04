#!/bin/sh
# Builds the extension zip for the judges, pointed at the hosted backend. Does not touch ./dist (your local build).
#
#   API_URL=https://scam-copilot-api.onrender.com ACCESS_TOKEN=<same as on the host> INBOUND_SECRET=<INBOUND_EMAIL_SECRET on the host> sh scripts/build-release.sh
# INBOUND_SECRET is optional: with it "Check this email" works without typing the secret into Settings.
#
# Output: release/scam-copilot-extension.zip (Load unpacked after unzipping, or attach it to a GitHub Release).
set -eu
: "${API_URL:?set API_URL to the hosted backend, e.g. https://scam-copilot-api.onrender.com}"
: "${ACCESS_TOKEN:?set ACCESS_TOKEN to the same value as on the host}"
API_URL="${API_URL%/}"
OUT="$(pwd)/release/extension"

rm -rf release && mkdir -p release
export VITE_API_URL="$API_URL" VITE_ACCESS_TOKEN="$ACCESS_TOKEN" VITE_INBOUND_SECRET="${INBOUND_SECRET:-}"
npx tsc -b
npx vite build --outDir "$OUT" --emptyOutDir
npx vite build -c vite.content.config.ts --outDir "$OUT"

# The manifest may call only the hosted backend (a build for localhost keeps http://localhost:8000/*).
API_URL="$API_URL" node -e '
const fs = require("fs"); const f = process.argv[1];
const m = JSON.parse(fs.readFileSync(f, "utf8"));
m.host_permissions = [process.env.API_URL + "/*"];
fs.writeFileSync(f, JSON.stringify(m, null, 4));
' "$OUT/manifest.json"

(cd "$OUT" && zip -qr ../scam-copilot-extension.zip .)
echo "built release/scam-copilot-extension.zip -> $API_URL"
