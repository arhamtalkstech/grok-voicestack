import { expect, test } from '@playwright/test'

// A real call: Chrome's microphone plays xAI-generated speech; the agent answers over xAI's
// realtime API; the Front Desk hands off to the Voice Specialist with context.
for (const mode of ['Direct', 'Relay'] as const) test(`${mode.toLowerCase()} voice call hands off from Front Desk to Voice Specialist and is saved`, async ({ page }) => {
  await page.goto('/settings')
  await page.getByPlaceholder('xai-…').nth(1).fill(process.env.XAI_API_KEY!)
  await page.getByRole('button', { name: 'Use for this session' }).click()
  await expect(page.getByText(/active · …/)).toBeVisible()

  await page.goto('/')
  await page.getByRole('button', { name: 'Start call' }).click()
  const dock = page.getByRole('complementary', { name: 'Live preview' })
  await dock.getByRole('radio', { name: mode }).click()
  await dock.getByRole('button', { name: 'Start call' }).click()

  // The entry agent greets, then the caller's question arrives through the fake microphone.
  const transcript = dock.getByRole('tabpanel')
  await expect(transcript.getByText('Thanks for calling', { exact: false })).toBeVisible({ timeout: 45_000 })
  await expect(transcript.getByText('dental clinic', { exact: false }).first()).toBeVisible({ timeout: 60_000 })

  // Handoff with the collected context, then the Voice Specialist speaks in its own turn.
  await expect(transcript.getByText(/use_case:/)).toBeVisible({ timeout: 60_000 })
  const specialistTurn = transcript.locator('div.max-w-\\[94\\%\\]').filter({ hasText: 'Voice Specialist' })
  await expect(specialistTurn.first()).toBeVisible({ timeout: 60_000 })
  await expect(dock.getByText('Voice Specialist', { exact: true }).first()).toBeVisible()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `test-results/live-handoff-${mode}.png` })

  await dock.getByRole('button', { name: 'End', exact: true }).click()
  await dock.getByRole('link', { name: 'Open conversation' }).click()
  const main = page.getByRole('main')
  await expect(main.getByText('Handoff', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(main.getByText('use_case:', { exact: false }).first()).toBeVisible()
  await expect(main.getByText('Summary', { exact: true })).toBeVisible({ timeout: 90_000 })
  await page.screenshot({ path: `test-results/live-conversation-${mode}.png`, fullPage: true })
})
