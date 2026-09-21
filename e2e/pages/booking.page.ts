import { Page, expect } from '@playwright/test';
import { bookingDate } from '../helpers/booking-date';

export class BookingPage {
  constructor(private page: Page) {}

  async open(doctorId: number) {
    // Tomorrow in the SERVER's timezone: see helpers/booking-date.ts for why "today" is not reliable.
    const bookingDay = bookingDate();
    await this.page.goto(`/doctor/${doctorId}/`);
    await this.page.locator('#appointment_date').evaluate((node: HTMLInputElement, dateValue) => {
      if ((node as any)._flatpickr) {
        (node as any)._flatpickr.setDate(dateValue, true);
        node.dispatchEvent(new Event('change'));
      } else {
        node.value = dateValue;
        node.dispatchEvent(new Event('change'));
      }
    }, bookingDay);
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
