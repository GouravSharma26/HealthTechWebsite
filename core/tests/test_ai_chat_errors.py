import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from django.core.cache import cache
from django.urls import reverse

ROOT = Path(__file__).resolve().parents[2]
KEY = 'gsk_test_key_1234567890'


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def ok_reply(content='Please see a general practitioner.'):
    return FakeResponse(200, {'choices': [{'message': {'content': content}}]})


@pytest.fixture(autouse=True)
def setup(settings, caplog):
    settings.GROQ_API_KEY = KEY
    cache.clear()
    caplog.set_level(logging.ERROR, logger='core.views')
    yield
    cache.clear()


def post_chat(client, message='hi'):
    return client.post(reverse('ai_chat'), json.dumps({'message': message}), content_type='application/json')


@pytest.mark.django_db
@patch('requests.post')
def test_success_path_is_unchanged(mock_post, client):
    mock_post.return_value = ok_reply()
    r = post_chat(client)
    assert r.status_code == 200 and r.json()['reply'] == 'Please see a general practitioner.'


@pytest.mark.django_db
@patch('requests.post')
def test_rejected_key_is_logged_and_user_gets_neutral_message(mock_post, client, caplog):
    body = '{"error":{"message":"Invalid API Key","type":"invalid_request_error","code":"invalid_api_key"}}'
    mock_post.return_value = FakeResponse(401, text=body)
    r = post_chat(client)
    assert r.status_code == 502
    assert r.json()['error'] == 'The AI assistant is temporarily unavailable. Please try again later.'
    assert 'high traffic' not in r.json()['error']          # no longer blames traffic for a bad key
    assert 'status=401' in caplog.text and 'invalid_api_key' in caplog.text and 'first call' in caplog.text


@pytest.mark.django_db
@patch('requests.post')
def test_unknown_model_400_is_logged(mock_post, client, caplog):
    mock_post.return_value = FakeResponse(404, text='{"error":{"message":"model not found"}}')
    r = post_chat(client)
    assert r.status_code == 502 and 'model not found' in caplog.text


@pytest.mark.django_db
@pytest.mark.parametrize('status', [429, 500, 503])
@patch('requests.post')
def test_rate_limit_and_outage_keep_the_high_traffic_message(mock_post, client, caplog, status):
    mock_post.return_value = FakeResponse(status, text='busy')
    r = post_chat(client)
    assert r.status_code == 500 and 'high traffic' in r.json()['error']
    assert f'status={status}' in caplog.text


@pytest.mark.django_db
@patch('requests.post')
def test_api_key_is_never_written_to_the_log(mock_post, client, caplog):
    mock_post.return_value = FakeResponse(401, text=f'bad key: {KEY}')
    post_chat(client)
    assert KEY not in caplog.text and '***' in caplog.text


@pytest.mark.django_db
@patch('requests.post')
def test_second_call_failure_falls_back_to_a_reply_instead_of_a_bare_error(mock_post, client, caplog):
    # A genuine second-call failure that ISN'T the tool_use_failed glitch (so no retry): the tool call already
    # found doctors, and the user should still get a reply rather than a bare error.
    tool_call = FakeResponse(200, {'choices': [{'message': {'content': None, 'tool_calls': [{
        'id': 'c1', 'function': {'name': 'find_doctors', 'arguments': '{"specialization": "Cardiology"}'}}]}}]})
    mock_post.side_effect = [tool_call, FakeResponse(400, text='{"error":{"message":"bad message shape"}}')]
    r = post_chat(client, 'my heart hurts')
    assert r.status_code == 200
    assert 'second call' in caplog.text and 'bad message shape' in caplog.text
    assert 'having trouble writing a full summary' in r.json()['reply']


@pytest.mark.django_db
@patch('requests.post', side_effect=requests.ConnectionError('dns failure'))
def test_network_errors_are_logged_with_traceback(mock_post, client, caplog):
    r = post_chat(client)
    assert r.status_code == 500 and 'unexpected error' in r.json()['error']
    rec = [x for x in caplog.records if 'ai_chat failed' in x.getMessage()]
    assert rec and rec[0].exc_info is not None


def test_api_keys_pasted_with_whitespace_are_stripped():
    code = "import healthtech.settings as s; print(repr(s.GROQ_API_KEY), repr(s.OPENROUTER_API_KEY))"
    r = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True,
                       env={'PATH': '', 'DJANGO_DEBUG': 'True', 'GROQ_API_KEY': ' gsk_abc \n',
                            'OPENROUTER_API_KEY': '\tsk-or-xyz '})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "'gsk_abc' 'sk-or-xyz'"
