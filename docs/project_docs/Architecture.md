# System Architecture & Application Flow

## 1. High-Level Architecture
HealthTechWebsite utilizes a modular, decoupled architecture prioritizing data isolation, security, and scalability.

- **Frontend / Client Layer:** Django HTML templates enhanced with Vanilla JavaScript and custom CSS frameworks focusing on Claymorphism/Glassmorphism for a premium UI feel. `FullCalendar` is utilized for robust client-side date management.
- **Backend / API Layer:** Django (MVT pattern) handling core business logic, strict role-based access control (RBAC), and RESTful internal API endpoints for dynamic UI updates.
- **Database Layer:** 
  - **PostgreSQL:** For all transactional data, user profiles, and appointment state machines (ACID compliant).
  - **Redis (Upstash):** Used by Django Channels for WebSocket state management (messaging, notifications) and rate-limit caching.
- **AI / External Integrations:** Isolated API calls to LLMs (e.g., Groq, OpenRouter) with robust data sanitization guardrails to prevent PHI leaks.

## 2. Data Flow & Security (PHI Handling)
1. **Data Ingestion:** All traffic is enforced via HTTPS (TLS 1.3). Forms and chat inputs utilize Django's built-in CSRF protection.
2. **Sanitization:** User inputs interacting with LLM features (AI Triage) are stripped of executable code and wrapped in defensive XML tags (`<user_input>`) to prevent prompt injection.
3. **Document Storage:** Sensitive documents (prescriptions, ID proofs) are stored in secure cloud buckets (e.g., Cloudinary) and served strictly through authenticated, signed URLs.
4. **Data Retrieval:** Database interactions exclusively use Django's ORM to prevent SQL injection. Serialized data is strictly filtered at the view layer based on `request.user` permissions.

## 3. Recommended Folder Structure
```text
HealthTechWebsite/
├── core/                   # Shared utilities, permissions, and base user models
│   ├── models/             # Separated model logic (Doctor, Patient, Slots)
│   ├── views/              # Dashboard and role-routing views
│   └── templates/core/     # Global UI components (base.html, doctorProfile.html)
├── appointments/           # Scheduling logic, calendars, state machines
├── messaging/              # WebSocket consumers, chat history and routing
├── ai_services/            # Isolated module for LLM API calls and prompt sanitization
│   ├── triage.py           # System prompts for non-diagnostic recommendations
│   └── scanner.py          # Vision-LLM prescription parsing
├── docs/
│   └── project_docs/       # PRD, Architecture, Rules, Phases, Design, Memory
├── static/                 # CSS (design system), JS, core assets
└── manage.py
```

## 4. Deployment Pipeline
The application uses **Render** for seamless PaaS hosting:
- **Web Service:** Runs via Gunicorn + Uvicorn workers (`uvicorn.workers.UvicornWorker`) to support ASGI WebSockets simultaneously with HTTP requests.
- **Database:** Connects directly to Neon Serverless Postgres.
- **Static Files:** Handled via Whitenoise during the build step (`collectstatic`).
