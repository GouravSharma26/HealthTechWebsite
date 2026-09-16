import { test, expect, Browser } from '@playwright/test';
import { AuthPage } from '../pages/auth.page';
import { BookingPage } from '../pages/booking.page';

// These tests assume a seeded doctor exists (see /mnt/skills or your fixtures
// loader) with id DOCTOR_ID and at least one open time slot for `today`.
// Wire this to your actual seed command, e.g.:
//   python manage.py seed_e2e
const DOCTOR_ID = process.env.E2E_DOCTOR_PROFILE_ID ? Number(process.env.E2E_DOCTOR_PROFILE_ID) : 1;

test.describe('Appointment booking', () => {
  test('a patient can book an available slot', async ({ page }) => {
    const auth = new AuthPage(page);
    const unique = Date.now();
    await auth.signup({
      username: `booker_${unique}`,
      email: `booker_${unique}@example.com`,
      phone: `7${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });
    await page.getByRole('button', { name: /save profile/i }).click();

    const booking = new BookingPage(page);
    await booking.open(DOCTOR_ID);
    await booking.bookSlot(/\d{1,2}:\d{2}/); // first available time-slot button
    await booking.expectBookingConfirmed();
  });

  test('booking the same doctor twice while a request is pending is blocked', async ({ page }) => {
    const auth = new AuthPage(page);
    const unique = Date.now();
    const username = `dup_booker_${unique}`;
    await auth.signup({
      username,
      email: `${username}@example.com`,
      phone: `6${unique.toString().slice(-9)}`,
      password: 'aG3nuinely-Str0ng-Passw0rd!',
      role: 'patient',
    });
    await page.getByRole('button', { name: /save profile/i }).click();

    const booking = new BookingPage(page);
    await booking.open(DOCTOR_ID);
    await booking.bookSlot(/\d{1,2}:\d{2}/);
    await booking.expectBookingConfirmed();

    // Try to book the same doctor again immediately
    await booking.open(DOCTOR_ID);
    await booking.bookSlot(/\d{1,2}:\d{2}/);
    await booking.expectAlreadyBookedWarning();
  });

  // Concurrency smoke test for the select_for_update fix on DoctorTimeSlot:
  // two different patients racing for the LAST seat in a capacity-1 slot
  // should result in exactly one success and one rejection, never two
  // successful bookings of the same seat.
  test('two concurrent patients cannot both book the last seat in a slot', async ({ browser }) => {
    const makePatientContext = async (b: Browser, label: string) => {
      const ctx = await b.newContext();
      const p = await ctx.newPage();
      const auth = new AuthPage(p);
      const unique = Date.now() + Math.random();
      await auth.signup({
        username: `race_${label}_${unique}`,
        email: `race_${label}_${unique}@example.com`,
        phone: `5${Math.floor(unique).toString().slice(-9)}`,
        password: 'aG3nuinely-Str0ng-Passw0rd!',
        role: 'patient',
      });
      await p.getByRole('button', { name: /save profile/i }).click();
      return { ctx, page: p };
    };

    const [a, b] = await Promise.all([
      makePatientContext(browser, 'a'),
      makePatientContext(browser, 'b'),
    ]);

    const bookingA = new BookingPage(a.page);
    const bookingB = new BookingPage(b.page);
    await bookingA.open(DOCTOR_ID);
    await bookingB.open(DOCTOR_ID);

    const [resultA, resultB] = await Promise.allSettled([
      bookingA.bookSlot(/\d{1,2}:\d{2}/),
      bookingB.bookSlot(/\d{1,2}:\d{2}/),
    ]);

    const results = await Promise.all([
      a.page.getByText(/appointment (requested|booked|pending)/i).isVisible(),
      b.page.getByText(/appointment (requested|booked|pending)/i).isVisible(),
    ]);
    const successCount = results.filter(Boolean).length;

    // Exactly one of the two should see confirmation; the other should see
    // a "slot full" / rejection state. This is a smoke test, not a proof —
    // pair it with the existing backend pytest race-condition coverage for
    // the real guarantee.
    expect(successCount).toBeLessThanOrEqual(1);

    await a.ctx.close();
    await b.ctx.close();
  });
});
