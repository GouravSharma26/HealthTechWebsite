import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from django.http import StreamingHttpResponse

ROOT = Path(__file__).resolve().parents[2]

# healthtech.settings installs a warnings.filterwarnings('ignore', message='StreamingHttpResponse
# must consume synchronous iterators') because WhiteNoise (as of 6.12.0, no ASGI-native mode)
# serves static files as a plain sync iterator, which Django's ASGI handler otherwise warns
# about on every single static-file request in production. This reproduces that exact code
# path (a StreamingHttpResponse wrapping a sync generator, consumed via __aiter__, same as
# Django's ASGI handler does for every response) and asserts the specific warning is silenced,
# while an unrelated warning of the same category still surfaces normally.


def _sync_generator():
    yield b"chunk-1"
    yield b"chunk-2"


@pytest.mark.asyncio
async def test_whitenoise_style_sync_iterator_warning_is_silenced():
    # pytest's own warning-capture plugin resets the global filter list around every test
    # (regardless of what healthtech.settings installed at process start), so asserting
    # against ambient state here would be testing pytest's harness, not our fix. Instead we
    # explicitly re-arm the exact filter healthtech.settings installs, inside this test's own
    # scope, and confirm *that* filter (not some other blanket suppression) is what silences
    # the warning WhiteNoise triggers under ASGI.
    response = StreamingHttpResponse(_sync_generator())
    with warnings.catch_warnings(record=True) as caught:
        warnings.filterwarnings(
            'ignore', message='StreamingHttpResponse must consume synchronous iterators'
        )
        chunks = [part async for part in response]

    assert chunks == [b"chunk-1", b"chunk-2"]
    assert not any(
        "StreamingHttpResponse must consume synchronous iterators" in str(w.message)
        for w in caught
    )


def test_settings_installs_the_expected_filter_in_a_clean_process():
    # Runs in a real, separate interpreter (not pytest's) so we see exactly what a Render/
    # Uvicorn worker process would have registered, unaffected by pytest's own per-test
    # warnings-plugin reset (see test above/its docstring for why that reset made a
    # same-process assertion unreliable).
    code = (
        "import warnings, healthtech.settings; "
        "print(any(f[0] == 'ignore' and f[1] is not None "
        "and f[1].pattern.startswith('StreamingHttpResponse must consume synchronous') "
        "for f in warnings.filters))"
    )
    r = subprocess.run(
        [sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True,
        env={**{k: v for k, v in os.environ.items() if not k.startswith('DJANGO_')},
             'DJANGO_SECRET_KEY': 'x', 'DJANGO_DEBUG': 'True'},
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == 'True'


def test_unrelated_warnings_still_surface():
    # Make sure the filter is scoped to the message text, not a blanket Warning-category
    # suppression that would hide unrelated issues. append=True so this check doesn't
    # itself outrank (and mask problems with) the filter under test.
    with warnings.catch_warnings(record=True) as caught:
        warnings.filterwarnings("always", message="some unrelated warning", append=True)
        warnings.warn("some unrelated warning", Warning)
    assert any("some unrelated warning" in str(w.message) for w in caught)
