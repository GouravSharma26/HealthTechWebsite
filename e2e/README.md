# HealthTech E2E Suite (Playwright)

## Why Playwright, not Cypress or plain Jest

- **Real WebSocket handshakes.** The chat feature runs on Django Channels; Cypress historically has weaker native WS support and Jest can't drive a real browser at all. Playwright drives real Chromium/WebKit and lets two independent browser *contexts* (separate cookie jars) talk to the same live server — needed to test "patient sends, doctor sees it live" as two genuinely separate sessions, not two tabs sharing one login.
- **Multi-context concurrency.** The booking race-condition smoke test needs two truly independent sessions racing the same request at once — this is a first-class Playwright feature (`browser.newContext()`), awkward in Cypress.
- Jest still owns component/unit-level frontend logic if you add any (currently none — the frontend is server-rendered templates + vanilla JS, so there's no component layer to unit test yet).

## Setup

```bash
cd e2e
npm ci
npx playwright install --with-deps chromium
```

Point it at a **disposable** database — these tests create real users, appointments, and chat messages:

```bash
# In the main repo, in a separate terminal:
cp .env.example .env.e2e
# edit .env.e2e to point at a throwaway DB (e.g. a local Postgres, not prod)
DATABASE_URL=... REDIS_URL=... python manage.py migrate
DATABASE_URL=... REDIS_URL=... python manage.py loaddata e2e_fixtures.json
DATABASE_URL=... REDIS_URL=... python -m daphne -b 127.0.0.1 -p 8000 healthtech.asgi:application
```

Then, from `e2e/`:

```bash
npm test              # headless, all browsers in playwright.config.ts
npm run test:headed   # watch it click through the UI
npm run test:ui       # Playwright's interactive test explorer — best for writing new tests
```

## What still needs wiring before these pass as-is

These are **starter specs**, written against the real routes/models in this repo, not a generic template — but three things are marked with `TODO`-equivalent comments and need your input to actually pass:

1. **`e2e_fixtures.json`** doesn't exist yet — create a Django fixture (or a `manage.py` seed command, mirroring `create_sample_data.py`) with at least one verified doctor, a login you control, and an open `DoctorTimeSlot` (the booking tests book for tomorrow in the server's timezone; set `E2E_SERVER_TZ` if it is not Asia/Kolkata) `chat.spec.ts` and `ai-features.spec.ts` reference `seeded_doctor_username` / `seeded_doctor_password` placeholders that need to point at that fixture.
2. **Selectors are best-effort.** I wrote these against Django's default form rendering (`getByLabel`) and common button text, but I haven't run them against the live templates — some `getByLabel`/`getByPlaceholder` calls will need a pass to match your actual `<label for=...>` and placeholder text exactly. Run `npx playwright test --ui` and use its selector picker to fix any misses quickly.
3. **`data-testid="doctor-card"`** in `ai-features.spec.ts` doesn't exist in `ai_chat.html` yet — add that attribute to the doctor-recommendation card markup (from the grounded-triage feature) so this test has a stable hook instead of relying on fragile text matching.

## Test coverage map

| File | Covers | Regression-guards for |
|---|---|---|
| `auth.spec.ts` | Signup, login, validation | Password-validator bypass, login brute-force gap (both fixed in the security audit) |
| `booking.spec.ts` | Appointment booking, double-booking prevention | `select_for_update` race-condition fix |
| `chat.spec.ts` | Real-time WebSocket delivery, HTTP fallback | Django Channels rollout; fallback-to-POST behavior |
| `ai-features.spec.ts` | Triage grounding, error states, prescription scan UX | `doc.user.id` vs `doc.id` bug; silent-empty-reply bug; `alert()` → inline error UX fix |

Deliberately **not** covered here (better tested at the unit/integration level, already covered by the existing `pytest` suite): prompt-injection defenses, rate-limiter math, the no-show model's leakage-safe training, CSWSH origin validation. Browser E2E tests are the wrong tool for those — keep them in `pytest`, where they already are.
