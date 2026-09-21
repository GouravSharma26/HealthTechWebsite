/**
 * The date the booking tests book for.
 *
 * The app runs in Asia/Kolkata (settings.TIME_ZONE) while CI runners are on UTC. The slots API treats a slot as
 * "passed" when its date is before today in the SERVER's timezone, or when it is today and its start time is
 * already over. Booking "today" therefore only works while the IST clock is between about 05:30 and 23:00:
 * outside that window the runner's date is a day behind the server's, or every seeded slot is already in the
 * past, and no slot button is enabled (the failure seen in CI when a run started at 01:45 IST).
 *
 * Booking TOMORROW, computed in the server's timezone, makes every seeded slot available at any time of day.
 * Set E2E_SERVER_TZ if the server under test runs in another timezone.
 */
export const SERVER_TZ = process.env.E2E_SERVER_TZ || 'Asia/Kolkata';

export function bookingDate(now: number = Date.now(), timeZone: string = SERVER_TZ): string {
  const tomorrow = new Date(now + 24 * 60 * 60 * 1000);
  // 'en-CA' formats as YYYY-MM-DD, which is what the date input and the slots API expect.
  return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(tomorrow);
}
