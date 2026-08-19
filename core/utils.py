import time
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse

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
