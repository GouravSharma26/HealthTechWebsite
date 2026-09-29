# Project Memory & Decision Log

*This document serves as the living memory of HealthTechWebsite. Use it to record architectural shifts, known technical debt, and major decisions to onboard new team members quickly.*

## 1. Architectural Decisions Log (ADR)
| Date | Decision | Rationale | Status |
| :--- | :--- | :--- | :--- |
| `2026-09-15` | Chose Django MVT over SPA (React) | Faster MVP iteration, built-in robust security features, and simpler auth management without managing complex JWTs. | Active |
| `2026-09-15` | Direct API Calls over LangChain | We use direct `requests` HTTP calls for AI integrations. LangChain is too heavy for our single-call triage endpoints and obscures prompt injection defenses. | Active |
| `2026-09-16` | Selected Render for Deployment | Offers managed PostgreSQL and zero-downtime deployments for rapid prototyping. Free tier supports Uvicorn ASGI workers. | Active |
| `2026-09-29` | Upgraded to Claymorphism UI | The legacy UI felt cluttered and stressful. A modern, soft, frosted-glass UI increases perceived trust and user satisfaction. | Active |
| `2026-09-29` | Migrated Slots to Responsive CSS Grid | Vertical stacking of 24-hour slots caused extreme page bloat. The internal scrollable grid fixes UX without requiring pagination. | Active |

## 2. Known Technical Debt
- **Doctor Search:** Currently using basic text/filter matching for doctors. Plan to migrate to `pgvector` or Elasticsearch for robust semantic search in Phase 3.
- **Notifications Polling:** WebSocket connections manage real-time updates, but fallback polling is somewhat aggressive on standard HTTP endpoints if WebSockets fail.

## 3. Compliance Milestones
- [x] Separate User types cleanly in database.
- [x] Implement prompt injection defenses on AI Triage.
- [ ] Implement end-to-end encryption for chat WebSockets database storage.
- [ ] Configure automatic expiration for Cloudinary signed URLs (Max 15 minutes).
- [ ] Establish BAA (Business Associate Agreement) with AI vendors (Groq, OpenRouter) before full public launch.
