# HealthTechWebsite

A working doctor–patient telehealth marketplace featuring custom authentication, appointment lifecycle management, in-app messaging, notifications, reviews, and secure AI-assisted triage and prescription scanning.

[Live Demo on Render](https://healthtech-web.onrender.com)

## Features

- **Doctor-Patient Marketplace**: Custom roles for patients and doctors.
- **Appointment Lifecycle**: Full state machine (pending → confirmed → cancel/reschedule requests → completed).
- **Messaging & Notifications**: Role-restricted in-app messaging and notification system.
- **Doctor Verification**: File uploads for licenses and degrees for review.
- **Automated Workflows**: Auto-approval jobs for scheduling.

### AI Features (Secure by Design)

This project includes two AI features that explicitly address prompt injection and safety:

1. **AI Triage Chatbot (Groq)**: Recommends a specialist type. The system prompt explicitly avoids providing diagnosis and wraps user input in defensive tags to prevent prompt injection.
2. **Vision-LLM Prescription Scanner (OpenRouter)**: Allows doctors to photograph a handwritten prescription to get structured medicines/instructions back. It includes an explicit defense against instructions hidden inside the image.

These features are framed as *assistance*, not *diagnosis*, and their security mechanisms are baked directly into the views.

## Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/GouravSharma26/HealthTechWebsite.git
cd HealthTechWebsite
```

### 2. Setup Virtual Environment & Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 3. Environment Variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Fill in the API keys (Groq, OpenRouter, Cloudinary) and email settings in the `.env` file.

### 4. Database Setup
```bash
python manage.py migrate
```

### 5. Run the Server
```bash
python manage.py runserver
```

## Deployment (Render + Neon + Upstash)

| Piece | Where | Notes |
|---|---|---|
| Web service | Render (free web service) | Build: `./build.sh` (installs deps, `collectstatic`, `migrate`). Start: `gunicorn healthtech.asgi:application -k uvicorn.workers.UvicornWorker --timeout 120`. The ASGI/Uvicorn worker is required: a plain WSGI worker cannot serve the chat / notification WebSockets. |
| Database | Neon Postgres | Use the *direct* connection string (host without `-pooler`). Free compute scales to zero, so the first request after idle is ~1s slower. Render's free Postgres expires after 30 days, which is why it is not used. |
| Redis | Upstash | Used by Channels (chat, notifications) and the rate-limit cache. `REDIS_URL` must be `rediss://default:<token>@<host>:6379` (TLS). The free tier has a monthly command quota and Channels polls Redis, so an idle open tab costs roughly 35k commands/day. |
| Files | Cloudinary | Uploaded documents / profile pictures. |
| AI | Groq, OpenRouter | Triage chat and prescription / lab-report scanning. |

Environment variables (set in the Render dashboard, never committed): `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`,
`DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `PYTHON_VERSION` (3.12.x, matches CI), `WEB_CONCURRENCY=2`
(the free plan has 512 MB), `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `CLOUDINARY_*`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`. Optional: `TRUSTED_PROXY_HOPS` (see below), `GROQ_MODEL` / `GROQ_MODEL_FALLBACKS`.

Notes:

- The app refuses to boot with `DJANGO_DEBUG=False` and no `DJANGO_SECRET_KEY`.
- `render.yaml` only applies if the service is linked to a Blueprint; otherwise the dashboard values are the source of truth.
- Semantic doctor search needs `torch` and is optional: `pip install -r requirements-search.txt`. Without it, search falls back to plain text matching.
- Rate limiting and login throttling key on the client IP from `X-Forwarded-For`. Set `TRUSTED_PROXY_HOPS` to the
  number of trusted proxies in front of the app so spoofed left-hand entries are ignored (default `0` = legacy
  first-entry behaviour). If Redis is unreachable these features fail open instead of taking the site down.
- The chatbot uses Groq's function calling. A key can only use the models enabled for its account: a 404
  `model_not_found` in the Render log means the model is retired or not available to that key. List the models a
  key can use with `GET https://api.groq.com/openai/v1/models` (Bearer token) and set `GROQ_MODEL` accordingly.
- Seed sample doctors on a fresh database: `DATABASE_URL=... SAMPLE_DATA_PASSWORD=... python create_sample_data.py`
  (a random password is generated and printed if `SAMPLE_DATA_PASSWORD` is unset).

## Architecture
See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed architecture decisions, including why we chose Django MVT and direct HTTP API calls over LangChain for our AI features.
