#!/usr/bin/env bash
# Re-download the xAI voice docs as markdown from docs.x.ai.
# Every docs.x.ai page has a markdown version at <page URL>.md.
# Usage: ./fetch.sh   (run from anywhere; writes next to this script)
set -euo pipefail

cd "$(dirname "$0")"
BASE="https://docs.x.ai"
TODAY="$(date +%Y-%m-%d)"

# local file | docs.x.ai path
PAGES='
guides/voice-overview.md|/developers/model-capabilities/audio/voice
guides/speech-to-speech.md|/developers/model-capabilities/audio/speech-to-speech
guides/speech-to-speech-sip.md|/developers/model-capabilities/audio/speech-to-speech/sip
guides/speech-to-speech-prompting-guide.md|/developers/model-capabilities/audio/speech-to-speech/prompting-guide
guides/text-to-speech.md|/developers/model-capabilities/audio/text-to-speech
guides/speech-to-text.md|/developers/model-capabilities/audio/speech-to-text
guides/custom-voices.md|/developers/model-capabilities/audio/custom-voices
guides/ephemeral-tokens.md|/developers/model-capabilities/audio/ephemeral-tokens
models/speech-to-speech.md|/developers/models/speech-to-speech
models/text-to-speech.md|/developers/models/text-to-speech
models/speech-to-text.md|/developers/models/speech-to-text
api-reference/voice.md|/developers/rest-api-reference/inference/voice
api-reference/speech-to-text.md|/developers/rest-api-reference/inference/speech-to-text
cookbook/voice-agent-web.md|/cookbook/examples/voice-agent-web
cookbook/voice-agent-webrtc.md|/cookbook/examples/voice-agent-webrtc
cookbook/voice-agent-phone.md|/cookbook/examples/voice-agent-phone
cookbook/voice-agent-mobile.md|/cookbook/examples/voice-agent-mobile
cookbook/live-interpreter.md|/cookbook/examples/live-interpreter
cookbook/meeting-to-action-items.md|/cookbook/examples/meeting-to-action-items
cookbook/podcast-from-a-link.md|/cookbook/examples/podcast-from-a-link
cookbook/video-dubbing.md|/cookbook/examples/video-dubbing
related/tools-overview.md|/developers/tools/overview
related/function-calling.md|/developers/tools/function-calling
related/web-search.md|/developers/tools/web-search
related/x-search.md|/developers/tools/x-search
related/collections-search.md|/developers/tools/collections-search
related/remote-mcp.md|/developers/tools/remote-mcp
related/collections.md|/developers/files/collections
related/collections-api.md|/developers/files/collections/api
related/regional-endpoints.md|/developers/advanced-api-usage/regions
related/rate-limits.md|/developers/rate-limits
related/pricing.md|/developers/pricing
'

failed=0
while IFS='|' read -r file path; do
  [ -z "$file" ] && continue
  mkdir -p "$(dirname "$file")"
  tmp="$(mktemp)"
  code="$(curl -sL -w '%{http_code}' -o "$tmp" "$BASE$path.md")"
  if [ "$code" != "200" ] || [ ! -s "$tmp" ] || grep -qi '<!doctype html' "$tmp"; then
    echo "FAILED $code $BASE$path.md" >&2
    failed=1
    rm -f "$tmp"
    continue
  fi
  {
    echo "<!-- Source: $BASE$path (markdown: $BASE$path.md), fetched $TODAY. Do not edit; re-run fetch.sh. -->"
    echo
    # Make site-relative links absolute so they work outside docs.x.ai.
    sed -E 's#\]\(/([^)]*)\)#](https://docs.x.ai/\1)#g' "$tmp"
  } > "$file"
  rm -f "$tmp"
  echo "ok  $file  ($(wc -c < "$file" | tr -d ' ') bytes)"
done <<< "$PAGES"

# Machine-readable WebSocket specs linked from the API reference (verbatim JSON).
mkdir -p specs
for spec in voice-realtime tts-streaming stt-streaming; do
  if curl -sfL -o "specs/$spec.ws.json" "$BASE/$spec.ws.json" && python3 -m json.tool "specs/$spec.ws.json" > /dev/null; then
    echo "ok  specs/$spec.ws.json  ($(wc -c < "specs/$spec.ws.json" | tr -d ' ') bytes)"
  else
    echo "FAILED $BASE/$spec.ws.json" >&2
    failed=1
  fi
done

exit "$failed"
