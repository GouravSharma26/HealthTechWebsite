import { defineConfig, devices } from '@playwright/test';

/**
 * HealthTech E2E suite config.
 * Run against a local `manage.py runserver` (Daphne, for WebSocket support)
 * pointed at a disposable test database — never against production data,
 * since these tests create real users, appointments, and chat messages.
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false, // booking/chat tests share DB state; keep serial per-file
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['html', { open: 'never' }], ['list']],

  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'] } }, // most patients will be on mobile
  ],
});
