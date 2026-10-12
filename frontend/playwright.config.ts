import { defineConfig } from '@playwright/test'
import path from 'node:path'

// Live browser test: needs XAI_API_KEY and a running instance (see docs/testing.md).
const callerWav = path.resolve('e2e/.cache/caller.wav')

export default defineConfig({
  testDir: 'e2e',
  timeout: 180_000,
  globalSetup: './e2e/global-setup.ts',
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    viewport: { width: 1440, height: 900 },
    permissions: ['microphone'],
    launchOptions: {
      channel: process.env.E2E_CHROME_CHANNEL ?? 'chrome',
      args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${callerWav}%noloop`, '--autoplay-policy=no-user-gesture-required'],
    },
  },
})
