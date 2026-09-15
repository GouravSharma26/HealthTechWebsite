# Contributing & Architecture Decisions

## Architecture Decisions

### 1. Django MVT over JS Frameworks
This project uses Django's Model-View-Template (MVT) architecture with server-rendered templates rather than a decoupled React/Vue frontend.
- **Why?** It keeps the stack simple and unified, allowing faster iteration on the core domain logic (appointments, scheduling, state machines) without the overhead of maintaining a separate API layer, state management, and CORS configuration.

### 2. Direct API Calls over LangChain
For our AI features (Groq text LLM and OpenRouter vision LLM), we use direct HTTP API calls via `requests` instead of heavy wrappers like LangChain.
- **Why?** Our AI integrations are single-call endpoints. We don't have complex multi-step reasoning chains or RAG pipelines. Using direct API calls reduces dependency bloat, makes the prompt injection defenses explicitly visible in the view code, and simplifies debugging.
