import logging
import re
import time
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
import os
import joblib
from django.conf import settings
from django.db.models import Q
from .models import Appointment, DoctorProfile

logger = logging.getLogger(__name__)

# Suffixes that differ between how a specialty is named vs. how its doctor is titled
# (Cardiology / Cardiologist, Pediatrics / Pediatrician, Psychiatry / Psychiatrist ...).
_SPECIALTY_SUFFIXES = sorted(['ologist', 'iatrist', 'ology', 'iatry', 'ician', 'ics', 'ist', 'ic', 'y'],
                             key=len, reverse=True)


def specialization_stem(term):
    """Reduce a specialty or doctor title to a shared stem: Cardiology / Cardiologist -> 'cardi'."""
    words = (term or '').strip().lower().split()
    if not words:
        return ''
    word = words[0]
    for suffix in _SPECIALTY_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def doctors_matching_specialization(term, limit=5):
    """Verified doctors whose specialization matches `term`, tolerant of Cardiology/Cardiologist mismatches."""
    term = (term or '').strip()
    if not term:
        return DoctorProfile.objects.none()
    query = Q(specialization__icontains=term)
    stem = specialization_stem(term)
    if stem and stem != term.lower():
        query |= Q(specialization__icontains=stem)
    return (DoctorProfile.objects.filter(query, is_verified=True)
            .select_related('user').order_by('-experience_years')[:limit])


def available_specializations(limit=25):
    """Distinct specializations of verified doctors, so the chatbot can pick a real one."""
    names = (DoctorProfile.objects.filter(is_verified=True).exclude(specialization='')
             .order_by('specialization').values_list('specialization', flat=True).distinct())
    return sorted({n.strip() for n in names if n and n.strip()})[:limit]



# Specialty stems too generic to infer a specialization from free text ("in general", "family").
_GENERIC_STEMS = {'general', 'family', 'internal', 'medicine', 'specialist'}


def clean_chat_history(history, limit=16, max_chars=2000):
    """Keep only well-formed user/assistant text turns, newest `limit`, each truncated.

    The chat endpoint is open to anonymous callers, so the history is untrusted input.
    """
    if not isinstance(history, list):
        return []
    cleaned = []
    for msg in history[-limit:]:
        if not isinstance(msg, dict):
            continue
        role, content = msg.get('role'), msg.get('content')
        if role in ('user', 'assistant') and isinstance(content, str) and content.strip():
            entry = {'role': role, 'content': content[:max_chars]}
            # The widget echoes back the specialization the server reported for a reply. It is
            # client-supplied, so it is only ever used after being checked against the real list.
            if role == 'assistant' and isinstance(msg.get('specialization'), str):
                entry['specialization'] = msg['specialization'][:100]
            if role == 'assistant' and msg.get('stage') in VALID_STAGES:
                entry['stage'] = msg['stage']
            cleaned.append(entry)
    return cleaned


def infer_specialization_from_history(history, available):
    """The most recently mentioned platform specialization in the conversation, or None.

    Lets a bare "can you suggest me any doctor" reuse what was already discussed.
    """
    import re
    canonical = {name.strip().lower(): name for name in available}
    for msg in reversed(history):                       # 1) what the server itself reported earlier
        claimed = (msg.get('specialization') or '').strip().lower()
        if claimed in canonical:
            return canonical[claimed]
    candidates = []
    for name in available:
        stem = specialization_stem(name)
        first_word = (name.split() or [''])[0].lower()
        if len(stem) >= 4 and stem not in _GENERIC_STEMS and first_word not in _GENERIC_STEMS:
            candidates.append((name, re.compile(r'\b' + re.escape(stem), re.IGNORECASE)))
    for msg in reversed(history):                       # 2) fall back to what the text mentions
        for name, pattern in candidates:
            if pattern.search(msg['content']):
                return name
    return None



# ---------------------------------------------------------------------------------------------
# Triage workflow helpers (see docs/triage-framework.md)
# ---------------------------------------------------------------------------------------------
MAX_FOLLOW_UPS = 4
VALID_STAGES = ('question', 'summary')

# Emergency indicators. This screen runs on every user message, independent of the AI model, so a
# possible emergency is never left to the model alone. Order = priority; at most 2 alerts are shown.
EMERGENCY_CATEGORIES = [
    ('consciousness', r"unconscious|passed out|not responding|unresponsive|seizure|convulsion|fainted",
     "Loss of consciousness or a seizure needs urgent help",
     "If someone is unresponsive, having a seizure, or has fainted and is not recovering, call 112 now and stay with them."),
    ('breathing', r"can'?t breathe|cannot breathe|trouble breathing|difficulty breathing|struggling to breathe|"
                  r"short(?:ness)? of breath|gasping|choking",
     "Trouble breathing needs urgent help",
     "If you are struggling to breathe, cannot speak in full sentences, or your lips look blue, call 112 now."),
    ('cardiac', r"chest (?:pain|pressure|tightness|hurts?|heaviness)|pain in (?:my |the )?chest|heart attack|crushing (?:pain|pressure)",
     "Chest symptoms can be serious",
     "If the pain is severe, spreads to your arm, jaw or back, or comes with breathlessness, sweating, nausea or "
     "faintness, call 112 now and do not drive yourself. Otherwise get checked by a doctor today."),
    ('stroke', r"face (?:is )?droop|drooping face|slurred speech|can'?t speak|sudden(?:ly)? (?:weak|numb|confus)|"
               r"numb(?:ness)? (?:on )?(?:one|my left|my right) side|sudden (?:loss of )?vision|worst headache",
     "These can be signs of a stroke",
     "Face drooping, arm weakness, slurred speech or sudden confusion: call 112 immediately and note the time the symptoms started."),
    ('bleeding', r"(?:severe|heavy|uncontrolled) bleeding|won'?t stop bleeding|bleeding (?:a lot|heavily)|"
                 r"(?:cough(?:ing)?|vomit(?:ing)?|throw(?:ing)? up) (?:up )?blood",
     "Heavy bleeding is an emergency",
     "Press firmly on the wound with a clean cloth and call 112 now. If you are coughing or vomiting blood, call 112 now."),
    ('allergy', r"(?:tongue|throat|lips|face) (?:is )?(?:swelling|swollen|closing)|anaphyla|throat closing",
     "This could be a severe allergic reaction",
     "Swelling of the lips, tongue or throat can block breathing. Call 112 now, and use any emergency allergy medicine "
     "already prescribed to you, as directed."),
    ('self_harm', r"suicid|kill myself|end my life|want to die|self[- ]harm|hurt myself|overdos|took too many (?:pills|tablets)",
     "You are not alone",
     "If you are thinking about harming yourself or you are in immediate danger, call 112 now or go to the nearest "
     "hospital, and please tell someone you trust so you are not alone right now."),
    ('poisoning', r"swallowed (?:poison|bleach|chemical)|poisoned",
     "Possible poisoning is an emergency",
     "Call 112 now. Do not make the person vomit unless emergency services tell you to, and keep the container to show them."),
]
_EMERGENCY_COMPILED = [(cat, re.compile(pattern, re.IGNORECASE), title, message)
                       for cat, pattern, title, message in EMERGENCY_CATEGORIES]
# A negation only counts when it sits directly in front of the symptom ("no chest pain"), so that
# "not sure if I have chest pain" still raises the alert: a missed emergency is worse than a false alarm.
_NEGATED = re.compile(
    r"(?:\b(?:no|without|never had|denies|denied|free of)"
    r"|\b(?:don'?t|do not|doesn'?t|does not|didn'?t|did not|haven'?t|have not|hasn'?t) (?:have|had|get|feel|experience)(?: any)?"
    r"|\bnot (?:having|experiencing)(?: any)?)\s+(?:any |a |the |much )?$", re.IGNORECASE)


def screen_for_emergency(text, limit=2):
    """Emergency indicators mentioned in `text`: [{'category', 'title', 'message'}], most urgent first."""
    text = text or ''
    found = []
    for category, pattern, title, message in _EMERGENCY_COMPILED:
        for match in pattern.finditer(text):
            if not _NEGATED.search(text[max(0, match.start() - 30):match.start()]):
                found.append({'category': category, 'title': title, 'message': message})
                break
    return found[:limit]


def count_follow_up_questions(history):
    """Follow-up questions the assistant has asked since the last final summary (from the client's stage marks)."""
    asked = 0
    for msg in reversed(history):
        if msg.get('role') != 'assistant':
            continue
        if msg.get('stage') == 'summary':
            break
        if msg.get('stage') == 'question':
            asked += 1
    return asked


_URGENCY_RE = re.compile(r"emergency status\W*(emergency|urgent|routine|self[- ]?care)", re.IGNORECASE)


def parse_urgency(reply):
    """Urgency level from the summary template's 'Emergency status' line, or None."""
    match = _URGENCY_RE.search(reply or '')
    if not match:
        return None
    return match.group(1).lower().replace('-', '_').replace(' ', '_') if 'care' not in match.group(1).lower() else 'self_care'



def get_client_ip(request):
    """Best-effort client IP behind a reverse proxy.

    With settings.TRUSTED_PROXY_HOPS = N > 0 the address is taken N entries from the right of
    X-Forwarded-For (the part the trusted proxies wrote); anything further left is
    client-supplied. With 0 the legacy behaviour is kept (first entry).
    """
    hops = getattr(settings, 'TRUSTED_PROXY_HOPS', 0)
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        parts = [p.strip() for p in xff.split(',') if p.strip()]
        if hops > 0 and len(parts) >= hops:
            return parts[-hops]
        if hops == 0 and parts:
            return parts[0]
    return request.META.get('REMOTE_ADDR')


# The cache backs rate limiting and login throttling. If it is unavailable (Redis down,
# hosted-Redis quota exhausted) these helpers degrade to "no limiting" instead of raising,
# so a cache outage can't turn into a login / AI-endpoint outage.
def safe_cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        logger.warning("cache.get failed for %r; continuing without it", key, exc_info=True)
        return default


def safe_cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        logger.warning("cache.set failed for %r; continuing without it", key, exc_info=True)


def safe_cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        logger.warning("cache.delete failed for %r; continuing without it", key, exc_info=True)


def rate_limit_ip(max_requests, time_window_seconds=60):
    """
    Simple IP-based rate limiter using Django's caching framework.
    Limits each IP to max_requests per time_window_seconds. Fails open if the cache is down.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            cache_key = f"rl_{view_func.__name__}_{get_client_ip(request)}"
            now = time.time()

            history = safe_cache_get(cache_key, []) or []
            history = [req_time for req_time in history if req_time > now - time_window_seconds]

            if len(history) >= max_requests:
                return JsonResponse({'error': 'Rate limit exceeded. Please wait a moment and try again.'}, status=429)

            history.append(now)
            safe_cache_set(cache_key, history, time_window_seconds)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

_MODEL = None
_MODEL_LOADED = False

def get_model():
    global _MODEL, _MODEL_LOADED
    if not _MODEL_LOADED:
        model_path = settings.NOSHOW_MODEL_PATH
        if os.path.exists(model_path):
            try:
                _MODEL = joblib.load(model_path)
            except Exception:
                _MODEL = None
        _MODEL_LOADED = True
    return _MODEL

def predict_risk(appointment):
    """
    Predicts the no-show risk for a given appointment.
    Returns: 'Low', 'Medium', 'High', or 'Insufficient Data'
    """
    model = get_model()
    if not model:
        return "Insufficient Data"
        
    lead_time = (appointment.date - appointment.created_at.date()).days
    if lead_time < 0: lead_time = 0
    
    created_time = appointment.created_at
    past_appts = Appointment.objects.filter(
        patient=appointment.patient, 
        created_at__lt=created_time,
        status__in=['Completed', 'Cancelled']
    )
    
    total_past = past_appts.count()
    if total_past == 0:
        return "Insufficient Data"
        
    canceled_past = past_appts.filter(status='Cancelled').count()
    past_cancel_rate = canceled_past / total_past
    
    day_of_week = appointment.date.weekday()
    time_of_day = appointment.time.hour if appointment.time else 12
    
    X = [[lead_time, past_cancel_rate, day_of_week, time_of_day]]
    
    try:
        idx = list(model.classes_).index(1) if 1 in model.classes_ else 1
        proba = model.predict_proba(X)[0][idx]
        
        if proba >= 0.7:
            return "High"
        elif proba >= 0.4:
            return "Medium"
        else:
            return "Low"
    except Exception:
        return "Insufficient Data"
