import { Page, expect } from '@playwright/test';

export class BookingPage {
  constructor(private page: Page) {}

  async open(doctorId: number) {
    const today = new Date().toISOString().split('T')[0];
    await this.page.goto(`/doctor/${doctorId}/?date=${today}`);
    // Wait a moment for slots to load via JS
    await this.page.waitForTimeout(500);
  }

  async bookSlot(slotLabel: string | RegExp) {
    await this.page.getByRole('button', { name: slotLabel }).click();
    await this.page.getByRole('button', { name: /confirm booking|book appointment/i }).click();
  }

  async expectBookingConfirmed() {
    await expect(this.page.getByText(/appointment (requested|booked|pending)/i)).toBeVisible();
  }

  async expectAlreadyBookedWarning() {
    await expect(this.page.getByText(/already have an active appointment/i)).toBeVisible();
  }
}
