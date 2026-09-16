import { Page, expect } from '@playwright/test';

export class BookingPage {
  constructor(private page: Page) {}

  async open(doctorId: number) {
    const d = new Date();
    const today = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    await this.page.goto(`/doctor/${doctorId}/`);
    await this.page.locator('#appointment_date').evaluate((node: HTMLInputElement, dateValue) => {
      if ((node as any)._flatpickr) {
        (node as any)._flatpickr.setDate(dateValue, true);
        node.dispatchEvent(new Event('change'));
      } else {
        node.value = dateValue;
        node.dispatchEvent(new Event('change'));
      }
    }, today);
    // Wait a moment for slots to load via JS
    await this.page.waitForTimeout(500);
  }

  async bookSlot(slotLabel: string | RegExp, useLast: boolean = false) {
    const slots = this.page.getByRole('button', { name: slotLabel }).and(this.page.locator(':not([disabled])'));
    const slotBtn = useLast ? slots.last() : slots.first();
    await slotBtn.click();
    await this.page.getByRole('button', { name: /confirm booking|book appointment/i }).click();
  }

  async expectBookingConfirmed() {
    await expect(this.page.getByText(/appointment (requested|booked|pending)/i)).toBeVisible();
  }

  async expectAlreadyBookedWarning() {
    await expect(this.page.getByText(/already have an active appointment/i)).toBeVisible();
  }
}
