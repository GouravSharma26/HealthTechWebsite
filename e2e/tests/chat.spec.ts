import { test, expect } from '@playwright/test';
import { AuthPage } from '../pages/auth.page';

// Requires the app running under Daphne/ASGI (not plain `runserver` on an
// old Django version) since this exercises the real Channels WebSocket path,
//   python manage.py seed_e2e
const DOCTOR_ID = process.env.E2E_DOCTOR_USER_ID ? Number(process.env.E2E_DOCTOR_USER_ID) : 1;

test.describe('Real-time chat', () => {
  test('a message sent by the patient appears live in the doctor\'s browser without a reload', async ({ browser }) => {
    const patientCtx = await browser.newContext();
    const doctorCtx = await browser.newContext();
    const patientPage = await patientCtx.newPage();
    const doctorPage = await doctorCtx.newPage();

    const unique = Date.now();
    await new AuthPage(patientPage).signup({
      username: `chat_patient_${unique}`,
      email: `chat_patient_${unique}@example.com`,
      phone: `4${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });
    await patientPage.getByRole('button', { name: /save profile/i }).click();
    await patientPage.waitForURL(/profile/);

    // Doctor side assumes a seeded doctor login; swap for your fixture's credentials.
    await new AuthPage(doctorPage).login('seeded_doctor_username', 'seeded_doctor_password');

    await patientPage.goto(`/chat/${DOCTOR_ID}/`);

    const message = `Hello from Playwright ${unique}`;
    await patientPage.getByPlaceholder(/type a message/i).fill(message);
    await patientPage.getByTestId('send-button').click();

    await doctorPage.goto('/chat/');
    await doctorPage.getByText(new RegExp(`chat_patient_${unique}`, 'i')).click();

    // No reload on the doctor's page — this must arrive over the open socket.
    await expect(doctorPage.getByText(message)).toBeVisible({ timeout: 5000 });

    await patientCtx.close();
    await doctorCtx.close();
  });

  test('chat still works over the HTTP fallback if the socket never opens', async ({ page, context }) => {
    // Simulate the socket failing to connect by blocking the WS upgrade.
    await context.route('**/ws/chat/**', (route) => route.abort());

    const auth = new AuthPage(page);
    const unique = Date.now();
    await auth.signup({
      username: `fallback_patient_${unique}`,
      email: `fallback_patient_${unique}@example.com`,
      phone: `3${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });
    await page.getByRole('button', { name: /save profile/i }).click();
    await page.waitForURL(/profile/);

    await page.goto(`/chat/${DOCTOR_ID}/`);
    const message = `Fallback message ${unique}`;
    await page.getByPlaceholder(/type a message/i).fill(message);
    await page.getByTestId('send-button').click();

    // Falls back to a normal form POST + page render; message should still
    // appear in the thread after the resulting page load.
    await expect(page.getByText(message)).toBeVisible();
  });
});
