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

## Architecture
See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed architecture decisions, including why we chose Django MVT and direct HTTP API calls over LangChain for our AI features.
