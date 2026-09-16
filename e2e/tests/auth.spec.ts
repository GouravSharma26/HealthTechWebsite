import { test, expect } from '@playwright/test';
import { AuthPage } from '../pages/auth.page';

test.describe('Authentication', () => {
  test('a patient can sign up and lands on the setup page', async ({ page }) => {
    const auth = new AuthPage(page);
    const unique = Date.now();
    await auth.signup({
      username: `patient_${unique}`,
      email: `patient_${unique}@example.com`,
      phone: `9${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });
    await expect(page).toHaveURL(/patient.*setup/i);
  });

  // Regression test for the signup password-validator bypass fixed in the
  // security audit: weak passwords must be rejected, not silently accepted.
  test('signup rejects a weak password', async ({ page }) => {
    const auth = new AuthPage(page);
    const unique = Date.now();
    await auth.signup({
      username: `weak_${unique}`,
      email: `weak_${unique}@example.com`,
      phone: `8${unique.toString().slice(-9)}`,
      password: '123',
      role: 'patient',
    });
    await expect(page).toHaveURL(/signup/);
    await expect(page.getByText(/too short|too common|entirely numeric/i).first()).toBeVisible();
  });

  test('login with wrong password shows an error and does not authenticate', async ({ page }) => {
    const auth = new AuthPage(page);
    await auth.login('nonexistent_user_xyz', 'wrong-password');
    await auth.expectLoginError(/invalid username or password/i);
  });

  // Regression test for the login brute-force gap fixed in the security
  // audit: repeated failed attempts from the same client must eventually
  // be throttled, independent of whether the credentials are ever correct.
  test('repeated failed logins trigger a lockout message', async ({ browser }) => {
    test.setTimeout(60000); // 10 sequential network requests can take a while
    const context = await browser.newContext({
      extraHTTPHeaders: { 'X-Forwarded-For': `192.168.1.${Math.floor(Math.random() * 255)}` }
    });
    const page = await context.newPage();
    const auth = new AuthPage(page);
    for (let i = 0; i < 11; i++) {
      await auth.login('lockout_target_user', 'wrong-password');
    }
    await auth.expectLoginError(/too many failed login attempts/i);
    await context.close();
  });
});
