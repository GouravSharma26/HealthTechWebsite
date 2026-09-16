import { Page, expect } from '@playwright/test';

export class AuthPage {
  constructor(private page: Page) {}

  async signup(opts: { username: string; email: string; phone: string; password: string; role: 'patient' | 'doctor' }) {
    await this.page.goto('/signup/');
    await this.page.getByRole('button', { name: new RegExp(opts.role, 'i'), exact: true }).click();
    await this.page.getByPlaceholder(/username/i).fill(opts.username);
    await this.page.getByPlaceholder(/email/i).fill(opts.email);
    await this.page.getByPlaceholder(/phone/i).fill(opts.phone);
    await this.page.getByPlaceholder(/password/i).fill(opts.password);
    await this.page.getByRole('button', { name: /sign ?up/i }).click();
  }

  async login(username: string, password: string) {
    await this.page.goto('/login/');
    await this.page.getByPlaceholder(/username/i).fill(username);
    await this.page.getByPlaceholder(/password/i).fill(password);
    await this.page.getByRole('button', { name: /log ?in/i }).click();
  }

  async expectLoggedIn() {
    // Adjust selector to whatever base.html actually renders for an authed nav state
    await expect(this.page.getByRole('link', { name: /logout/i })).toBeVisible();
  }

  async expectLoginError(message: string | RegExp) {
    await expect(this.page.getByText(message)).toBeVisible();
  }
}
