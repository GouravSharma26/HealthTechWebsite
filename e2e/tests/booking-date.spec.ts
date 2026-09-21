import { test, expect } from '@playwright/test';
import { bookingDate } from '../helpers/booking-date';

// Pure logic: no browser, no server. Guards the time-of-day bug where booking "today" only worked between
// about 05:30 and 23:00 IST.
const at = (iso: string) => Date.parse(iso);

// The date, in `tz`, of the instant `t` (YYYY-MM-DD).
const dateIn = (t: number, tz: string) =>
  new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(t));

test.describe('booking date helper', () => {
  test('is tomorrow in the server timezone for the run times seen in CI', () => {
    expect(bookingDate(at('2026-09-20T15:09:00Z'), 'Asia/Kolkata')).toBe('2026-09-21'); // 20:39 IST (passing run)
    expect(bookingDate(at('2026-09-20T17:45:00Z'), 'Asia/Kolkata')).toBe('2026-09-21'); // 23:15 IST
    expect(bookingDate(at('2026-09-20T20:15:00Z'), 'Asia/Kolkata')).toBe('2026-09-22'); // 01:45 IST on the 21st (failing run)
    expect(bookingDate(at('2026-09-21T03:00:00Z'), 'Asia/Kolkata')).toBe('2026-09-22'); // 08:30 IST
  });

  test('is always exactly one day after the server\'s current date, at every half hour', () => {
    const start = at('2026-12-30T00:00:00Z'); // also crosses a month and a year boundary
    for (let i = 0; i < 24 * 2 * 4; i++) {
      const t = start + i * 30 * 60 * 1000;
      const today = dateIn(t, 'Asia/Kolkata');
      const expected = new Date(Date.parse(today + 'T00:00:00Z') + 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
      expect(bookingDate(t, 'Asia/Kolkata'), `at ${new Date(t).toISOString()}`).toBe(expected);
    }
  });

  test('respects another server timezone and is formatted YYYY-MM-DD', () => {
    expect(bookingDate(at('2026-09-20T20:15:00Z'), 'UTC')).toBe('2026-09-21');
    expect(bookingDate(at('2026-09-20T20:15:00Z'), 'America/New_York')).toBe('2026-09-21');
    expect(bookingDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
