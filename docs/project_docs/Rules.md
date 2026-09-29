# Development & AI-Assistance Guidelines

## 1. Security & Compliance (HIPAA/GDPR Principles)
- **Zero-Trust Access:** Always verify `request.user` permissions at the view level before rendering templates, executing state changes, or returning JSON. Do not rely solely on hiding buttons in the UI.
- **PHI Handling:** Protected Health Information (PHI) must never be logged to stdout, APM tools, error trackers (like Sentry), or sent unmasked to external non-BAA covered APIs.
- **Data Deletion:** Implement soft deletes (`is_active = False`) for medical records and user profiles to maintain audit trails while complying with GDPR right-to-be-forgotten requests.
- **Audit Logging:** Critical actions (prescriptions written, appointments cancelled, doctor approvals changed) must be timestamped and logged within the database.

## 2. AI-Assisted Development Rules
- **Prompt Injection Defense:** Any user-generated content sent to an LLM must be wrapped in strict system prompt constraints and XML tags (e.g., `<user_input>`).
- **No Diagnostics:** AI features must include hardcoded guardrails refusing to provide definitive medical diagnoses or prescribe controlled substances.
- **Code Generation Review:** When using AI tools to write code, developers must manually audit the output for:
  - SQL injection vulnerabilities (ensure ORM usage).
  - XSS (ensure Django template auto-escaping is NOT bypassed with `|safe` unless explicitly sanitized).
  - CSRF tokens on all POST forms.

## 3. Coding Standards
- **Python:** Adhere to PEP 8 guidelines. Use type hints for all complex service layer functions.
- **Database:** Actively avoid N+1 query problems; use `select_related` and `prefetch_related` for nested models (e.g., fetching a Doctor and their related User object).
- **Frontend:** Keep JavaScript modular. Avoid inline styles where possible; utilize the centralized CSS design system (`index.css`) to maintain the Claymorphism UI consistency.
