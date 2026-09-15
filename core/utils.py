import time
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
import os
import joblib
from django.conf import settings
from .models import Appointment

def rate_limit_ip(max_requests, time_window_seconds=60):
    """
    Simple IP-based rate limiter using Django's caching framework.
    Limits each IP to max_requests per time_window_seconds.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
                
            cache_key = f"rl_{view_func.__name__}_{ip}"
            
            # Get current request history
            history = cache.get(cache_key, [])
            now = time.time()
            
            # Filter out requests older than the time window
            history = [req_time for req_time in history if req_time > now - time_window_seconds]
            
            if len(history) >= max_requests:
                return JsonResponse({'error': 'Rate limit exceeded. Please wait a moment and try again.'}, status=429)
                
            # Add current request and save back to cache
            history.append(now)
            cache.set(cache_key, history, time_window_seconds)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

_MODEL = None
_MODEL_LOADED = False

def get_model():
    global _MODEL, _MODEL_LOADED
    if not _MODEL_LOADED:
        model_path = os.path.join(settings.BASE_DIR, 'core', 'ml_models', 'noshow_model.joblib')
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
