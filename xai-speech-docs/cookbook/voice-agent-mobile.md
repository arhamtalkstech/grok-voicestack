<!-- Source: https://docs.x.ai/cookbook/examples/voice-agent-mobile (markdown: https://docs.x.ai/cookbook/examples/voice-agent-mobile.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->


# Mobile Voice Apps

These two native apps, one for iOS and one for Android, hold real-time voice conversations with Grok through the Grok API. They're a starting point for adding a voice assistant to a mobile app.

Two native apps built on the [Voice Agent API](https://docs.x.ai/developers/model-capabilities/audio/voice). Each folder's README covers setup.

- [`swift/`](https://github.com/xai-org/xai-cookbook/blob/main/examples/voice-agent-mobile/swift/): a SwiftUI app for iOS and macOS with text-to-speech, streaming text-to-speech, and real-time voice agents. Open `VoiceTesterApp.xcodeproj` in Xcode 16 or newer.
- [`kotlin/`](https://github.com/xai-org/xai-cookbook/blob/main/examples/voice-agent-mobile/kotlin/): an Android app for real-time voice conversations and text messaging with Grok. Open it in Android Studio.

Both are for learning and aren't production-ready as-is. In a real app, fetch short-lived [ephemeral tokens](https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens) from your backend instead of putting an API key in the client.
