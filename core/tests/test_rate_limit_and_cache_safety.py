import pytest
from unittest.mock import patch
from django.core.cache import cache
from django.http import JsonResponse
from django.test import RequestFactory, override_settings
from django.urls import reverse

from core.models import User
from core.utils import get_client_ip, rate_limit_ip

rf = RequestFactory()


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def make_limited_view(limit=5):
    @rate_limit_ip(max_requests=limit, time_window_seconds=60)
    def view(request):
        return JsonResponse({'ok': True})
    return view


# ---- get_client_ip -------------------------------------------------------------------------
def req(xff=None):
    extra = {'HTTP_X_FORWARDED_FOR': xff} if xff else {}
    return rf.get('/x', REMOTE_ADDR='10.1.1.1', **extra)


def test_default_keeps_legacy_first_entry():
    assert get_client_ip(req('9.9.9.9, 1.2.3.4')) == '9.9.9.9'


@override_settings(TRUSTED_PROXY_HOPS=1)
def test_one_trusted_proxy_uses_rightmost_entry_and_ignores_spoofed_left():
    assert get_client_ip(req('6.6.6.6, 1.2.3.4')) == '1.2.3.4'


@override_settings(TRUSTED_PROXY_HOPS=2)
def test_two_trusted_proxies_use_second_from_right():
    assert get_client_ip(req('6.6.6.6, 1.2.3.4, 172.16.0.9')) == '1.2.3.4'


@override_settings(TRUSTED_PROXY_HOPS=3)
def test_fewer_entries_than_hops_falls_back_to_remote_addr():
    assert get_client_ip(req('1.2.3.4')) == '10.1.1.1'


def test_no_header_uses_remote_addr():
    assert get_client_ip(req()) == '10.1.1.1'


# ---- rate limiter --------------------------------------------------------------------------
def test_limiter_blocks_after_limit():
    view = make_limited_view(5)
    codes = [view(req('9.9.9.9')).status_code for _ in range(7)]
    assert codes == [200] * 5 + [429] * 2


def test_legacy_mode_can_be_bypassed_by_rotating_first_xff_entry():
    # documents WHY TRUSTED_PROXY_HOPS exists
    view = make_limited_view(3)
    assert [view(req(f'10.0.0.{i}, 1.2.3.4')).status_code for i in range(6)] == [200] * 6


@override_settings(TRUSTED_PROXY_HOPS=1)
def test_rotating_spoofed_xff_does_not_bypass_limit_when_hops_configured():
    view = make_limited_view(3)
    assert [view(req(f'10.0.0.{i}, 1.2.3.4')).status_code for i in range(6)] == [200] * 3 + [429] * 3


def test_limiter_fails_open_when_cache_is_down():
    view = make_limited_view(1)
    with patch('core.utils.cache') as broken:
        broken.get.side_effect = ConnectionError('redis down')
        broken.set.side_effect = ConnectionError('redis down')
        assert [view(req('9.9.9.9')).status_code for _ in range(3)] == [200, 200, 200]


def test_view_errors_are_not_swallowed_by_the_limiter():
    @rate_limit_ip(max_requests=5)
    def boom(request):
        raise ValueError('real bug')
    with pytest.raises(ValueError):
        boom(req('9.9.9.9'))


# ---- login must keep working when the cache is down ----------------------------------------
@pytest.mark.django_db
def test_login_still_works_when_cache_is_down(client):
    User.objects.create_user(username='cachedown', password='Xk9!veryStrongPw2026', is_patient=True)
    with patch('core.utils.cache') as broken:
        for m in ('get', 'set', 'delete'):
            getattr(broken, m).side_effect = ConnectionError('redis down')
        r = client.post(reverse('login'), {'username': 'cachedown', 'password': 'Xk9!veryStrongPw2026'})
    assert r.status_code == 302            # redirected after successful login, not a 500


@pytest.mark.django_db
def test_login_brute_force_lockout_still_works_with_cache_up(client):
    User.objects.create_user(username='victim', password='Xk9!veryStrongPw2026', is_patient=True)
    for _ in range(10):
        client.post(reverse('login'), {'username': 'victim', 'password': 'wrong'})
    r = client.post(reverse('login'), {'username': 'victim', 'password': 'Xk9!veryStrongPw2026'})
    assert r.status_code == 200            # locked out: login page re-rendered, not redirected
    assert b'Too many failed login attempts' in r.content


# ---- search API is now rate limited ---------------------------------------------------------
@pytest.mark.django_db
def test_search_api_is_rate_limited(client):
    with patch('core.search.get_model', return_value=None):
        codes = [client.get(reverse('api_search_doctors'), {'q': 'x'}).status_code for _ in range(32)]
    assert codes[:30] == [200] * 30 and codes[30:] == [429, 429]
