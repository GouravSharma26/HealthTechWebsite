import logging
import time
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
import os
import joblib
from django.conf import settings
from .models import Appointment

logger = logging.getLogger(__name__)

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
