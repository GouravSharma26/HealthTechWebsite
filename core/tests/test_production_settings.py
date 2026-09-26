import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_settings(**env):
    """Import healthtech.settings in a clean subprocess with the given environment."""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith('DJANGO_') and k not in ('DEBUG', 'DATABASE_URL', 'REDIS_URL')}
    code = ("import healthtech.settings as s; "
            "print(s.DEBUG, getattr(s, 'SECURE_SSL_REDIRECT', None), getattr(s, 'SECURE_PROXY_SSL_HEADER', None), "
            "getattr(s, 'SECURE_HSTS_SECONDS', None), getattr(s, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', None), "
            "getattr(s, 'SECURE_HSTS_PRELOAD', None))")
    return subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True,
                          text=True, env={**base, **env})


def test_production_trusts_render_proxy_header_when_redirecting_to_https():
    # Render terminates TLS and sends X-Forwarded-Proto. If Django isn't told to trust it,
    # SECURE_SSL_REDIRECT redirects https -> https in an endless loop.
    r = load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY='x')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == (
        "False True ('HTTP_X_FORWARDED_PROTO', 'https') 3600 False False"
    )


def test_production_refuses_to_boot_without_secret_key():
    r = load_settings(DJANGO_DEBUG='False')
    assert r.returncode != 0
    assert 'DJANGO_SECRET_KEY' in r.stderr


def test_production_enables_hsts_with_a_conservative_default():
    # SECURE_SSL_REDIRECT already forces every request onto HTTPS, so a short default
    # HSTS window is safe out of the box; INCLUDE_SUBDOMAINS/PRELOAD stay off until
    # someone opts in deliberately (they can't be un-set for returning visitors).
    r = load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY='x')
    assert r.returncode == 0, r.stderr
    # SECURE_PROXY_SSL_HEADER prints as a tuple containing its own space, so pull the
    # last 3 whitespace-separated tokens (hsts_seconds, include_subdomains, preload)
    # from the right rather than splitting the whole line left-to-right.
    *_, hsts_seconds, include_subdomains, preload = r.stdout.strip().rsplit(' ', 3)
    assert int(hsts_seconds) > 0
    assert include_subdomains == 'False'
    assert preload == 'False'


def test_production_hsts_seconds_configurable_via_env():
    r = load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY='x', SECURE_HSTS_SECONDS='604800')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith('604800 False False')


def test_development_does_not_set_hsts():
    r = load_settings(DJANGO_DEBUG='True')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith('None None None')
