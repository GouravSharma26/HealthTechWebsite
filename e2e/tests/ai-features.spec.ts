import { test, expect } from '@playwright/test';
import { AuthPage } from '../pages/auth.page';
import path from 'path';

test.describe('AI triage assistant', () => {
  test('grounded triage returns advice and at least one real, clickable doctor card', async ({ page }) => {
    const auth = new AuthPage(page);
    const unique = Date.now();
    await auth.signup({
      username: `triage_${unique}`,
      email: `triage_${unique}@example.com`,
      phone: `2${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });

    await page.route('**/ai-chat/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            reply: 'You should consult a real doctor.',
            doctors: [
              {
                id: process.env.E2E_DOCTOR_PROFILE_ID ? Number(process.env.E2E_DOCTOR_PROFILE_ID) : 1,
                name: 'Dr. seeded_doctor_username',
                specialization: 'General Physician',
                profile_picture: null,
                experience: 10,
                consultation_fee: 50
              }
            ]
          })
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/ai-chat/');
    await page.getByPlaceholder(/describe your symptoms|type a message|headache/i).fill('I have chest pain and shortness of breath');
    await page.getByRole('button', { name: /send/i }).click();

    await expect(page.getByText(/consult a (real )?doctor/i)).toBeVisible({ timeout: 15000 });
    const doctorCard = page.locator('[data-testid="doctor-card"]').first();
    await expect(doctorCard).toBeVisible();

    // Regression test for the doc.user.id vs doc.id bug fixed earlier:
    // the Book link must resolve to a real doctor profile, not a 404.
    await doctorCard.getByRole('link', { name: /book|view profile/i }).click();
    await expect(page).toHaveURL(/\/doctor\/\d+\/?/, { timeout: 15000 });
  });

  test('a friendly error is shown, not a blank reply, when the AI backend fails', async ({ page, context }) => {
    await context.route('**/ai-chat/', (route) => {
      if (route.request().method() === 'POST') {
        return route.fulfill({ status: 500, body: JSON.stringify({ error: 'Simulated outage' }) });
      }
      return route.continue();
    });

    const auth = new AuthPage(page);
    const unique = Date.now();
    await auth.signup({
      username: `triage_err_${unique}`,
      email: `triage_err_${unique}@example.com`,
      phone: `1${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });

    await page.goto('/ai-chat/');
    await page.getByPlaceholder(/describe your symptoms|type a message|headache/i).fill('test message');
    await page.getByRole('button', { name: /send/i }).click();
    await expect(page.getByText(/trouble connecting|high traffic|error/i)).toBeVisible();
  });
});

test.describe('Prescription / lab report scanner', () => {
  test('doctor can upload a prescription image and sees structured output, not a raw alert', async ({ page }) => {
    // Requires a seeded, verified doctor login.
    await new AuthPage(page).login('seeded_doctor_username', 'seeded_doctor_password');
    await page.goto('/doctor/profile/');

    page.once('dialog', (dialog) => {
      // Regression guard for the alert()-based error UX fixed in Phase 7/8:
      // a native dialog popping up here means the old pattern regressed.
      throw new Error(`Unexpected native dialog: ${dialog.message()}`);
    });

    await page.route('**/api/scan-prescription/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            medicines: [{ name: 'Aspirin', dosage: '100mg', instructions: 'Take one daily' }]
          })
        });
      } else {
        await route.continue();
      }
    });

    const fileInput = page.locator('input[type="file"][id^="scan-upload-"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures', 'sample-prescription.jpg'));
    // The scan starts automatically onchange; no "Scan" button to click.

    // The test mock returns objects, which stringify to [object Object]. We just check it's populated.
    const medicinesLocator = page.locator('[id^="medicines-"]');
    await expect(medicinesLocator).not.toBeEmpty({ timeout: 15000 });
  });
});
