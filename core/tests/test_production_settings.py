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
            "print(s.DEBUG, s.SECURE_SSL_REDIRECT, getattr(s, 'SECURE_PROXY_SSL_HEADER', None))")
    return subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True,
                          text=True, env={**base, **env})


def test_production_trusts_render_proxy_header_when_redirecting_to_https():
    # Render terminates TLS and sends X-Forwarded-Proto. If Django isn't told to trust it,
    # SECURE_SSL_REDIRECT redirects https -> https in an endless loop.
    r = load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY='x')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False True ('HTTP_X_FORWARDED_PROTO', 'https')"


def test_production_refuses_to_boot_without_secret_key():
    r = load_settings(DJANGO_DEBUG='False')
    assert r.returncode != 0
    assert 'DJANGO_SECRET_KEY' in r.stderr
